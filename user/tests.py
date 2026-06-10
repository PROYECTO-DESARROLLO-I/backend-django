from datetime import timedelta

from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from administrative.models import Administrative
from doctor.models import Doctor
from headquarters.models import Headquarters
from patient.models import Patient
from specialties.models import Specialty
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


class InternalStaffRegisterTests(APITestCase):
    def setUp(self):
        self.url = reverse("staff-register")
        self.admin_user = User.objects.create_user(
            email="admin-registro@clinica.test",
            password="ClaveSegura123*",
            nombre="Admin",
            apellido="Registro",
            rol=User.Role.ADMINISTRATIVE,
        )
        Administrative.objects.create(
            user=self.admin_user,
            identity_document="100000001",
            position="Admisiones",
        )
        self.specialty = Specialty.objects.create(name="Medicina general")

    def authenticate_as_admin(self):
        self.client.force_authenticate(user=self.admin_user)

    def valid_doctor_payload(self, **overrides):
        payload = {
            "nombre": "Carlos",
            "apellido": "Mendoza",
            "email": "doctor@clinica.test",
            "rol": User.Role.DOCTOR,
            "identity_document": "222222222",
            "password": "MedicoSeguro123*",
            "specialties": [self.specialty.id],
            "register_number": "RM-12345",
            "academic_information": "Universidad Nacional",
            "phone_number": "3001234567",
        }
        payload.update(overrides)
        return payload

    def valid_administrative_payload(self, **overrides):
        payload = {
            "nombre": "Laura",
            "apellido": "Perez",
            "email": "administrativa@clinica.test",
            "rol": User.Role.ADMINISTRATIVE,
            "identity_document": "333333333",
            "generate_temporary_password": True,
            "position": "Recepción",
        }
        payload.update(overrides)
        return payload

    def test_administrative_user_can_create_doctor_with_required_fields(self):
        self.authenticate_as_admin()

        response = self.client.post(self.url, self.valid_doctor_payload(), format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["detail"], "Cuenta interna creada exitosamente.")
        self.assertNotIn("temporary_password", response.data["user"])
        user = User.objects.get(email="doctor@clinica.test")
        self.assertEqual(user.rol, User.Role.DOCTOR)
        self.assertTrue(user.check_password("MedicoSeguro123*"))
        doctor = user.doctor_profile
        self.assertEqual(doctor.identity_document, "222222222")
        self.assertEqual(doctor.register_number, "RM-12345")
        self.assertEqual(
            list(doctor.specialties.values_list("id", flat=True)),
            [self.specialty.id],
        )

    def test_administrative_user_can_create_internal_user_with_temporary_password(self):
        self.authenticate_as_admin()

        response = self.client.post(
            self.url,
            self.valid_administrative_payload(),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        temporary_password = response.data["user"]["temporary_password"]
        user = User.objects.get(email="administrativa@clinica.test")
        self.assertEqual(user.rol, User.Role.ADMINISTRATIVE)
        self.assertTrue(user.check_password(temporary_password))
        self.assertNotEqual(user.password, temporary_password)
        self.assertEqual(user.administrative_profile.identity_document, "333333333")

    def test_doctor_registration_requires_specialty_and_register_number(self):
        self.authenticate_as_admin()
        payload = self.valid_doctor_payload()
        payload.pop("specialties")
        payload.pop("register_number")

        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("specialties", response.data)
        self.assertIn("register_number", response.data)
        self.assertFalse(User.objects.filter(email="doctor@clinica.test").exists())

    def test_internal_user_registration_rejects_duplicate_email_and_document(self):
        self.authenticate_as_admin()
        Patient.objects.create(
            user=User.objects.create_user(
                email="paciente-doc@clinica.test",
                password="ClaveSegura123*",
                nombre="Paciente",
                apellido="Duplicado",
                rol=User.Role.PATIENT,
            ),
            identity_document="444444444",
            document_type=Patient.DocumentType.CC,
            date_birth="1990-01-01",
        )

        duplicate_email_response = self.client.post(
            self.url,
            self.valid_administrative_payload(email=self.admin_user.email),
            format="json",
        )
        duplicate_document_response = self.client.post(
            self.url,
            self.valid_administrative_payload(
                email="otro-admin@clinica.test",
                identity_document="444444444",
            ),
            format="json",
        )

        self.assertEqual(
            duplicate_email_response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertIn("email", duplicate_email_response.data)
        self.assertEqual(
            duplicate_document_response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertIn("identity_document", duplicate_document_response.data)

    def test_only_administrative_users_can_access_staff_registration(self):
        doctor_user = User.objects.create_user(
            email="medico-auth@clinica.test",
            password="ClaveSegura123*",
            nombre="Medico",
            apellido="Auth",
            rol=User.Role.DOCTOR,
        )
        Doctor.objects.create(
            user=doctor_user,
            identity_document="555555555",
            register_number="RM-AUTH",
        )

        anonymous_response = self.client.post(
            self.url,
            self.valid_administrative_payload(email="anonimo@clinica.test"),
            format="json",
        )
        self.client.force_authenticate(user=doctor_user)
        doctor_response = self.client.post(
            self.url,
            self.valid_administrative_payload(email="sin-permiso@clinica.test"),
            format="json",
        )

        self.assertEqual(anonymous_response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(doctor_response.status_code, status.HTTP_403_FORBIDDEN)
