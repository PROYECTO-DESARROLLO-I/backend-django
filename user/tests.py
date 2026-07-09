from datetime import timedelta

from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework import status
from rest_framework.test import APITestCase

from administrative.models import Administrative
from headquarters.models import Headquarters
from user.authentication import decode_access_token
from user.models import User


class AuthenticationLoginTests(APITestCase):
    def setUp(self):
        self.url = reverse("auth-login")
        self.password = "ClaveSegura123*"

    def create_user(self, **kwargs):
        defaults = {
            "email": "usuario@clinica.test",
            "password": self.password,
            "nombre": "Ana",
            "apellido": "Gomez",
            "rol": User.Role.PATIENT,
        }
        defaults.update(kwargs)
        return User.objects.create_user(**defaults)

    def login(self, email="usuario@clinica.test", password=None):
        return self.client.post(
            self.url,
            {
                "email": email,
                "password": password or self.password,
            },
            format="json",
        )

    def test_successful_login_returns_jwt_pair_role_and_user_context(self):
        headquarters = Headquarters.objects.create(
            name="Sede Norte",
            address="Calle 1 # 2-3",
            phone="3000000000",
        )
        user = self.create_user(
            email="admin@clinica.test",
            rol=User.Role.ADMINISTRATIVE,
        )
        Administrative.objects.create(
            user=user,
            headquarters=headquarters,
            position="Recepción",
        )

        response = self.login(email="admin@clinica.test")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["token_type"], "Bearer")
        self.assertEqual(response.data["expires_in"], 3600)
        self.assertEqual(response.data["refresh_expires_in"], 604800)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)
        self.assertEqual(response.data["user"]["rol"], User.Role.ADMINISTRATIVE)
        self.assertEqual(
            response.data["user"]["clinic_context"]["headquarters"],
            [{"id": headquarters.id, "name": "Sede Norte"}],
        )

        payload = decode_access_token(response.data["access"])
        self.assertEqual(str(payload["user_id"]), str(user.id))
        self.assertEqual(payload["rol"], User.Role.ADMINISTRATIVE)
        self.assertEqual(
            payload["clinic_context"]["headquarters"],
            [{"id": headquarters.id, "name": "Sede Norte"}],
        )

    def test_invalid_password_returns_generic_error_and_increments_attempts(self):
        user = self.create_user()

        response = self.login(password="incorrecta")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data["detail"], "Credenciales inválidas")
        self.assertNotIn("access", response.data)
        self.assertNotIn("refresh", response.data)
        user.refresh_from_db()
        self.assertEqual(user.failed_login_attempts, 1)
        self.assertIsNone(user.locked_until)

    def test_temporarily_locks_account_after_five_failed_attempts(self):
        user = self.create_user()

        for _ in range(4):
            response = self.login(password="incorrecta")
            self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

        response = self.login(password="incorrecta")

        self.assertEqual(response.status_code, 423)
        self.assertEqual(
            response.data["detail"],
            "Cuenta temporalmente bloqueada. Intente más tarde.",
        )
        self.assertIn("retry_after_seconds", response.data)
        user.refresh_from_db()
        self.assertEqual(user.failed_login_attempts, 5)
        self.assertIsNotNone(user.locked_until)
        self.assertGreater(user.locked_until, timezone.now())

        response = self.login()
        self.assertEqual(response.status_code, 423)
        self.assertNotIn("access", response.data)
        self.assertNotIn("refresh", response.data)

    def test_successful_login_resets_failed_attempts_and_expired_lock(self):
        user = self.create_user()
        user.failed_login_attempts = 4
        user.locked_until = timezone.now() - timedelta(minutes=1)
        user.save(update_fields=["failed_login_attempts", "locked_until", "updated_at"])

        response = self.login()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        user.refresh_from_db()
        self.assertEqual(user.failed_login_attempts, 0)
        self.assertIsNone(user.locked_until)
        self.assertIsNotNone(user.last_login)

    def test_inactive_account_does_not_receive_token(self):
        user = self.create_user(is_active=False)

        response = self.login()

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["detail"], "No fue posible iniciar sesión")
        self.assertNotIn("access", response.data)
        self.assertNotIn("refresh", response.data)
        user.refresh_from_db()
        self.assertEqual(user.failed_login_attempts, 0)


class AuthenticationEndpointTests(APITestCase):
    def setUp(self):
        self.password = "ClaveSegura123*"
        self.user = User.objects.create_user(
            email="usuario@clinica.test",
            password=self.password,
            nombre="Ana",
            apellido="Gomez",
            rol=User.Role.PATIENT,
        )
        self.login_url = reverse("auth-login")
        self.logout_url = reverse("auth-logout")
        self.me_url = reverse("auth-me")
        self.refresh_url = reverse("token-refresh")
        self.verify_url = reverse("token-verify")

    def login(self):
        return self.client.post(
            self.login_url,
            {"email": self.user.email, "password": self.password},
            format="json",
        )

    def authenticate(self, access):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

    def test_me_returns_authenticated_user_context(self):
        login_response = self.login()
        self.authenticate(login_response.data["access"])

        response = self.client.get(self.me_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], self.user.id)
        self.assertEqual(response.data["email"], self.user.email)
        self.assertEqual(response.data["rol"], User.Role.PATIENT)
        self.assertEqual(response.data["clinic_context"], {"headquarters": [], "profile": None})
        self.assertNotIn("password", response.data)

    def test_me_requires_authentication(self):
        response = self.client.get(self.me_url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_token_verify_accepts_valid_access_token(self):
        login_response = self.login()

        response = self.client.post(
            self.verify_url,
            {"token": login_response.data["access"]},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_token_verify_rejects_invalid_token(self):
        response = self.client.post(
            self.verify_url,
            {"token": "token.invalido"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_token_refresh_returns_new_access_and_rotated_refresh(self):
        login_response = self.login()

        response = self.client.post(
            self.refresh_url,
            {"refresh": login_response.data["refresh"]},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)
        payload = decode_access_token(response.data["access"])
        self.assertEqual(str(payload["user_id"]), str(self.user.id))
        self.assertEqual(payload["rol"], User.Role.PATIENT)

    def test_token_refresh_rejects_invalid_token(self):
        response = self.client.post(
            self.refresh_url,
            {"refresh": "token.invalido"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_token_refresh_blacklists_previous_refresh_after_rotation(self):
        login_response = self.login()
        original_refresh = login_response.data["refresh"]

        first_response = self.client.post(
            self.refresh_url,
            {"refresh": original_refresh},
            format="json",
        )
        second_response = self.client.post(
            self.refresh_url,
            {"refresh": original_refresh},
            format="json",
        )

        self.assertEqual(first_response.status_code, status.HTTP_200_OK)
        self.assertEqual(second_response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_logout_blacklists_refresh_token(self):
        login_response = self.login()
        access = login_response.data["access"]
        refresh = login_response.data["refresh"]
        self.authenticate(access)

        response = self.client.post(
            self.logout_url,
            {"refresh": refresh},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["detail"], "Sesión cerrada correctamente")
        refresh_response = self.client.post(
            self.refresh_url,
            {"refresh": refresh},
            format="json",
        )
        self.assertEqual(refresh_response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_logout_requires_authenticated_access_token(self):
        login_response = self.login()

        response = self.client.post(
            self.logout_url,
            {"refresh": login_response.data["refresh"]},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_logout_requires_refresh_token_body(self):
        login_response = self.login()
        self.authenticate(login_response.data["access"])

        response = self.client.post(self.logout_url, {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["detail"], "Token de cierre de sesión requerido")

    def test_logout_rejects_invalid_refresh_token(self):
        login_response = self.login()
        self.authenticate(login_response.data["access"])

        response = self.client.post(
            self.logout_url,
            {"refresh": "token.invalido"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["detail"], "No fue posible cerrar la sesión")

    def test_logout_rejects_refresh_token_from_another_user(self):
        other_user = User.objects.create_user(
            email="otra@clinica.test",
            password=self.password,
            nombre="Otra",
            apellido="Persona",
            rol=User.Role.PATIENT,
        )
        own_login_response = self.login()
        other_login_response = self.client.post(
            self.login_url,
            {"email": other_user.email, "password": self.password},
            format="json",
        )
        self.authenticate(own_login_response.data["access"])

        response = self.client.post(
            self.logout_url,
            {"refresh": other_login_response.data["refresh"]},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["detail"], "No fue posible cerrar la sesión")


class PasswordResetRequestTests(APITestCase):
    def setUp(self):
        self.url = reverse("password-reset-request")
        self.password = "ClaveSegura123*"

    def create_user(self, **kwargs):
        defaults = {
            "email": "usuario@clinica.test",
            "password": self.password,
            "nombre": "Ana",
            "apellido": "Gomez",
            "rol": User.Role.PATIENT,
        }
        defaults.update(kwargs)
        return User.objects.create_user(**defaults)

    def test_registered_email_returns_generic_message_and_sends_email(self):
        user = self.create_user()

        response = self.client.post(self.url, {"email": user.email}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["detail"],
            "Si el correo está registrado, se ha enviado un enlace de recuperación.",
        )
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(user.email, mail.outbox[0].to)

    def test_unregistered_email_returns_same_generic_message_and_no_email(self):
        response = self.client.post(
            self.url, {"email": "noexiste@clinica.test"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["detail"],
            "Si el correo está registrado, se ha enviado un enlace de recuperación.",
        )
        self.assertEqual(len(mail.outbox), 0)

    def test_invalid_email_format_returns_bad_request(self):
        response = self.client.post(
            self.url, {"email": "no-es-un-correo"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_inactive_user_returns_generic_message_and_no_email(self):
        user = self.create_user(is_active=False)

        response = self.client.post(self.url, {"email": user.email}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["detail"],
            "Si el correo está registrado, se ha enviado un enlace de recuperación.",
        )
        self.assertEqual(len(mail.outbox), 0)

    def test_email_body_contains_reset_link_with_uid_and_token(self):
        user = self.create_user()

        response = self.client.post(self.url, {"email": user.email}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(mail.outbox), 1)
        body = mail.outbox[0].body
        self.assertIn("uid=", body)
        self.assertIn("token=", body)


class PasswordResetConfirmTests(APITestCase):
    def setUp(self):
        self.url = reverse("password-reset-confirm")
        self.login_url = reverse("auth-login")
        self.password = "ClaveSegura123*"
        self.user = User.objects.create_user(
            email="usuario@clinica.test",
            password=self.password,
            nombre="Ana",
            apellido="Gomez",
            rol=User.Role.PATIENT,
        )

    def build_uid_and_token(self, user=None):
        user = user or self.user
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        return uid, token

    def confirm(self, uid, token, new_password="NuevaClave123", confirm_password=None):
        return self.client.post(
            self.url,
            {
                "uid": uid,
                "token": token,
                "new_password": new_password,
                "confirm_password": (
                    confirm_password if confirm_password is not None else new_password
                ),
            },
            format="json",
        )

    def test_valid_token_and_password_updates_password(self):
        uid, token = self.build_uid_and_token()

        response = self.confirm(uid, token, "NuevaClave123", "NuevaClave123")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["detail"],
            "Tu contraseña ha sido actualizada exitosamente.",
        )
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("NuevaClave123"))

    def test_reusing_same_token_after_success_returns_bad_request(self):
        uid, token = self.build_uid_and_token()
        first_response = self.confirm(uid, token, "NuevaClave123", "NuevaClave123")
        self.assertEqual(first_response.status_code, status.HTTP_200_OK)

        second_response = self.confirm(uid, token, "OtraClave456", "OtraClave456")

        self.assertEqual(second_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            second_response.data["detail"],
            "El enlace de recuperación es inválido o ha expirado.",
        )

    def test_corrupted_token_returns_generic_bad_request(self):
        uid, _ = self.build_uid_and_token()

        response = self.confirm(uid, "token-invalido", "NuevaClave123", "NuevaClave123")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data["detail"],
            "El enlace de recuperación es inválido o ha expirado.",
        )

    def test_corrupted_uid_returns_generic_bad_request(self):
        _, token = self.build_uid_and_token()

        response = self.confirm(
            "uid-invalido", token, "NuevaClave123", "NuevaClave123"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data["detail"],
            "El enlace de recuperación es inválido o ha expirado.",
        )

    @override_settings(PASSWORD_RESET_TIMEOUT=-1)
    def test_expired_token_returns_generic_bad_request(self):
        uid, token = self.build_uid_and_token()

        response = self.confirm(uid, token, "NuevaClave123", "NuevaClave123")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data["detail"],
            "El enlace de recuperación es inválido o ha expirado.",
        )

    def test_mismatched_passwords_returns_bad_request(self):
        uid, token = self.build_uid_and_token()

        response = self.confirm(uid, token, "NuevaClave123", "OtraClave456")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_password_shorter_than_8_characters_returns_bad_request(self):
        uid, token = self.build_uid_and_token()

        response = self.confirm(uid, token, "Corta1", "Corta1")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_password_without_digits_returns_bad_request(self):
        uid, token = self.build_uid_and_token()

        response = self.confirm(uid, token, "ClaveSinNumeros", "ClaveSinNumeros")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_login_works_with_new_password_after_reset(self):
        uid, token = self.build_uid_and_token()
        reset_response = self.confirm(uid, token, "NuevaClave123", "NuevaClave123")
        self.assertEqual(reset_response.status_code, status.HTTP_200_OK)

        login_response = self.client.post(
            self.login_url,
            {"email": self.user.email, "password": "NuevaClave123"},
            format="json",
        )

        self.assertEqual(login_response.status_code, status.HTTP_200_OK)
        self.assertIn("access", login_response.data)

    def test_locked_user_is_unlocked_after_successful_reset(self):
        self.user.failed_login_attempts = 5
        self.user.locked_until = timezone.now() + timedelta(minutes=15)
        self.user.save(
            update_fields=["failed_login_attempts", "locked_until", "updated_at"]
        )
        uid, token = self.build_uid_and_token()

        response = self.confirm(uid, token, "NuevaClave123", "NuevaClave123")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.failed_login_attempts, 0)
        self.assertIsNone(self.user.locked_until)

    def test_inactive_user_returns_generic_bad_request_and_password_unchanged(self):
        uid, token = self.build_uid_and_token()
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])

        response = self.confirm(uid, token, "NuevaClave123", "NuevaClave123")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data["detail"],
            "El enlace de recuperación es inválido o ha expirado.",
        )
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(self.password))
