from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.models import update_last_login
from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from user.authentication import (
    build_authenticated_user_payload,
    create_auth_tokens,
    get_access_token_lifetime_seconds,
    get_refresh_token_lifetime_seconds,
)
from user.permissions import IsAdministrativeUser
from user.serializers import (
    InternalStaffRegisterSerializer,
    LoginSerializer,
    LogoutSerializer,
)
from user.serializers import PatientRegisterSerializer

INVALID_CREDENTIALS_MESSAGE = "Credenciales inválidas"
INACTIVE_ACCOUNT_MESSAGE = "No fue posible iniciar sesión"
LOCKED_ACCOUNT_MESSAGE = "Cuenta temporalmente bloqueada. Intente más tarde."
LOGOUT_SUCCESS_MESSAGE = "Sesión cerrada correctamente"
LOGOUT_REQUIRED_TOKEN_MESSAGE = "Token de cierre de sesión requerido"
LOGOUT_ERROR_MESSAGE = "No fue posible cerrar la sesión"


class LoginView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = get_user_model().objects.normalize_email(
            serializer.validated_data["email"]
        )
        password = serializer.validated_data["password"]
        now = timezone.now()

        with transaction.atomic():
            user = (
                get_user_model()
                .objects.select_for_update()
                .filter(email__iexact=email)
                .first()
            )

            if user is None:
                check_password(password, make_password(None))
                return self._invalid_credentials_response()

            if user.login_lock_expired(now):
                user.reset_failed_login_attempts()

            if user.is_temporarily_locked(now):
                return self._locked_response(user, now)

            if not user.check_password(password):
                user.register_failed_login(now)
                if user.is_temporarily_locked(now):
                    return self._locked_response(user, now)
                return self._invalid_credentials_response()

            if not user.is_active:
                return Response(
                    {"detail": INACTIVE_ACCOUNT_MESSAGE},
                    status=status.HTTP_403_FORBIDDEN,
                )

            if user.failed_login_attempts or user.locked_until:
                user.reset_failed_login_attempts()

            update_last_login(None, user)
            tokens = create_auth_tokens(user)

        return Response(
            {
                "access": tokens["access"],
                "refresh": tokens["refresh"],
                "token_type": "Bearer",
                "expires_in": get_access_token_lifetime_seconds(),
                "expires_at": tokens["expires_at"].isoformat(),
                "refresh_expires_in": get_refresh_token_lifetime_seconds(),
                "refresh_expires_at": tokens["refresh_expires_at"].isoformat(),
                "user": build_authenticated_user_payload(user),
            },
            status=status.HTTP_200_OK,
        )

    def _invalid_credentials_response(self):
        return Response(
            {"detail": INVALID_CREDENTIALS_MESSAGE},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    def _locked_response(self, user, now):
        retry_after_seconds = max(1, int((user.locked_until - now).total_seconds()))
        return Response(
            {
                "detail": LOCKED_ACCOUNT_MESSAGE,
                "retry_after_seconds": retry_after_seconds,
                "locked_until": user.locked_until.isoformat(),
            },
            status=423,
        )


class LogoutView(APIView):
    def post(self, request):
        serializer = LogoutSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"detail": LOGOUT_REQUIRED_TOKEN_MESSAGE},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            refresh = RefreshToken(serializer.validated_data["refresh"])
            if str(refresh.get("user_id")) != str(request.user.id):
                return Response(
                    {"detail": LOGOUT_ERROR_MESSAGE},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            refresh.blacklist()
        except TokenError:
            return Response(
                {"detail": LOGOUT_ERROR_MESSAGE},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {"detail": LOGOUT_SUCCESS_MESSAGE},
            status=status.HTTP_200_OK,
        )


class MeView(APIView):
    def get(self, request):
        return Response(
            build_authenticated_user_payload(request.user),
            status=status.HTTP_200_OK,
        )
    
class PatientRegisterView(APIView):
    """
    POST /api/auth/register/
    Registro público de nuevos pacientes.
    No requiere autenticación.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = PatientRegisterSerializer(data=request.data)

        if serializer.is_valid(): #Si los datos son validos, guarda el nuevo paciente y user en la BDD
            serializer.save()
            return Response(
                {"detail": "Registro exitoso. Ya puedes iniciar sesión."},
                status=status.HTTP_201_CREATED
            )

        return Response( #Si los datos no son validos, devuelve error
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST
        )


class InternalStaffRegisterView(APIView):
    """
    POST /api/auth/staff/register/
    Registro de nuevas cuentas internas para médicos y administrativos.
    Requiere autenticación con rol Administrativo.
    """

    permission_classes = [IsAdministrativeUser]

    def post(self, request):
        serializer = InternalStaffRegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(
            {
                "detail": "Cuenta interna creada exitosamente.",
                "user": serializer.to_representation(user),
            },
            status=status.HTTP_201_CREATED,
        )

