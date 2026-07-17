from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from eps.models import EPS
from user.models import User

from .models import Patient
from .serializers import PatientRegistrationSerializer

User = get_user_model()


class PatientModelTests(TestCase):
    """Pruebas para el modelo Patient"""

    def setUp(self):
        """Configuración inicial para las pruebas"""
        self.user = User.objects.create_user(
            email="paciente@test.com",
            password="TestPassword123!",
            nombre="Juan",
            apellido="García",
            rol=User.Role.PATIENT,
        )

        self.eps = EPS.objects.create(
            name="SURA",
            code="SURA001",
            active=True,
        )

    def test_create_patient(self):
        """Test: Crear un paciente correctamente"""
        patient = Patient.objects.create(
            user=self.user,
            identity_document="12345678",
            document_type=Patient.DocumentType.CC,
            date_birth=date(1990, 5, 15),
            phone_number="3015551234",
            address="Calle 1 #2-3",
            eps=self.eps,
        )

        self.assertEqual(patient.user, self.user)
        self.assertEqual(patient.identity_document, "12345678")
        self.assertEqual(patient.document_type, Patient.DocumentType.CC)
        self.assertEqual(patient.date_birth, date(1990, 5, 15))
        self.assertEqual(patient.phone_number, "3015551234")
        self.assertEqual(patient.address, "Calle 1 #2-3")
        self.assertEqual(patient.eps, self.eps)

    def test_patient_string_representation(self):
        """Test: Representación en string del paciente"""
        patient = Patient.objects.create(
            user=self.user,
            identity_document="12345678",
            document_type=Patient.DocumentType.CC,
            date_birth=date(1990, 5, 15),
            phone_number="3015551234",
            address="Calle 1 #2-3",
            eps=self.eps,
        )

        expected_str = "Juan García - 12345678"
        self.assertEqual(str(patient), expected_str)

    def test_patient_one_to_one_relationship(self):
        """Test: Relación OneToOne entre User y Patient"""
        patient = Patient.objects.create(
            user=self.user,
            identity_document="12345678",
            document_type=Patient.DocumentType.CC,
            date_birth=date(1990, 5, 15),
            phone_number="3015551234",
            address="Calle 1 #2-3",
            eps=self.eps,
        )

        # Acceder al paciente desde el usuario
        self.assertEqual(self.user.patient_profile, patient)

    def test_identity_document_unique_constraint(self):
        """Test: El documento de identidad debe ser único"""
        Patient.objects.create(
            user=self.user,
            identity_document="12345678",
            document_type=Patient.DocumentType.CC,
            date_birth=date(1990, 5, 15),
            phone_number="3015551234",
            address="Calle 1 #2-3",
            eps=self.eps,
        )

        # Intentar crear otro paciente con el mismo documento
        user2 = User.objects.create_user(
            email="otro@test.com",
            password="TestPassword123!",
            nombre="Pedro",
            apellido="López",
            rol=User.Role.PATIENT,
        )

        with self.assertRaises(Exception):
            Patient.objects.create(
                user=user2,
                identity_document="12345678",  # Mismo documento
                document_type=Patient.DocumentType.CC,
                date_birth=date(1992, 10, 20),
                phone_number="3015555678",
                address="Carrera 10 #20-30",
                eps=self.eps,
            )


class PatientRegistrationSerializerTests(TestCase):
    """Pruebas para el serializer PatientRegistrationSerializer"""

    def setUp(self):
        """Configuración inicial para las pruebas"""
        self.eps = EPS.objects.create(
            name="SURA",
            code="SURA001",
            active=True,
        )

    def test_valid_patient_registration(self):
        """Test: Registro válido de paciente con todos los datos"""
        data = {
            "user": {
                "email": "nuevo_paciente@test.com",
                "password": "SecurePassword123!",
                "nombre": "Carlos",
                "apellido": "Martínez",
            },
            "identity_document": "87654321",
            "document_type": Patient.DocumentType.CC,
            "date_birth": "1985-03-20",
            "phone_number": "3105559876",
            "address": "Carrera 5 #10-15",
            "eps": self.eps.id,
        }

        serializer = PatientRegistrationSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)

        patient = serializer.save()

        # Verificar que se creó el usuario correctamente
        self.assertIsNotNone(patient.user)
        self.assertEqual(patient.user.email, "nuevo_paciente@test.com")
        self.assertEqual(patient.user.nombre, "Carlos")
        self.assertEqual(patient.user.apellido, "Martínez")
        self.assertEqual(patient.user.rol, User.Role.PATIENT)

        # Verificar que se creó el paciente correctamente
        self.assertEqual(patient.identity_document, "87654321")
        self.assertEqual(patient.document_type, Patient.DocumentType.CC)
        self.assertEqual(patient.date_birth, date(1985, 3, 20))
        self.assertEqual(patient.phone_number, "3105559876")
        self.assertEqual(patient.address, "Carrera 5 #10-15")
        self.assertEqual(patient.eps, self.eps)

    def test_future_date_birth_validation(self):
        """Test: Validación - Fecha de nacimiento no puede ser futura"""
        tomorrow = date.today() + timedelta(days=1)

        data = {
            "user": {
                "email": "futuro@test.com",
                "password": "SecurePassword123!",
                "nombre": "Ana",
                "apellido": "Gómez",
            },
            "identity_document": "11111111",
            "document_type": Patient.DocumentType.CC,
            "date_birth": tomorrow.isoformat(),  # Fecha futura en formato str
            "phone_number": "3105551111",
            "address": "Calle 1 #1-1",
            "eps": self.eps.id,
        }

        serializer = PatientRegistrationSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("date_birth", serializer.errors)
        self.assertIn("futura", str(serializer.errors["date_birth"][0]).lower())

    def test_today_date_birth_validation(self):
        """Test: Validación - Fecha de nacimiento hoy es válida"""
        today = date.today()

        data = {
            "user": {
                "email": "hoy@test.com",
                "password": "SecurePassword123!",
                "nombre": "Bebé",
                "apellido": "Recién",
            },
            "identity_document": "22222222",
            "document_type": Patient.DocumentType.CC,
            "date_birth": today.isoformat(),  # Hoy es válido
            "phone_number": "3105552222",
            "address": "Calle 2 #2-2",
            "eps": self.eps.id,
        }

        serializer = PatientRegistrationSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        
        patient = serializer.save()
        self.assertEqual(patient.date_birth, today)

    def test_invalid_eps_id(self):
        """Test: Validación - EPS inválida o inexistente"""
        data = {
            "user": {
                "email": "eps_invalida@test.com",
                "password": "SecurePassword123!",
                "nombre": "Laura",
                "apellido": "Pérez",
            },
            "identity_document": "33333333",
            "document_type": Patient.DocumentType.CC,
            "date_birth": "1990-01-01",
            "phone_number": "3105553333",
            "address": "Calle 3 #3-3",
            "eps": 99999,  # ID inexistente
        }

        serializer = PatientRegistrationSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("eps", serializer.errors)

    def test_inactive_eps_not_allowed(self):
        """Test: Validación - EPS inactiva no debe permitirse"""
        inactive_eps = EPS.objects.create(
            name="COMPENSAR",
            code="COMP001",
            active=False,
        )

        data = {
            "user": {
                "email": "eps_inactiva@test.com",
                "password": "SecurePassword123!",
                "nombre": "Roberto",
                "apellido": "Silva",
            },
            "identity_document": "44444444",
            "document_type": Patient.DocumentType.CC,
            "date_birth": "1992-06-10",
            "phone_number": "3105554444",
            "address": "Calle 4 #4-4",
            "eps": inactive_eps.id,
        }

        serializer = PatientRegistrationSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("eps", serializer.errors)

    def test_missing_required_user_fields(self):
        """Test: Validación - Faltan campos requeridos de usuario"""
        data = {
            "user": {
                "email": "incompleto@test.com",
                "password": "SecurePassword123!",
                # Faltan 'nombre' y 'apellido'
            },
            "identity_document": "55555555",
            "document_type": Patient.DocumentType.CC,
            "date_birth": "1994-12-05",
            "phone_number": "3105555555",
            "address": "Calle 5 #5-5",
            "eps": self.eps.id,
        }

        serializer = PatientRegistrationSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("user", serializer.errors)

    def test_missing_required_eps(self):
        """Test: Validación - EPS es requerida"""
        data = {
            "user": {
                "email": "sin_eps@test.com",
                "password": "SecurePassword123!",
                "nombre": "Miguel",
                "apellido": "Fernández",
            },
            "identity_document": "66666666",
            "document_type": Patient.DocumentType.CC,
            "date_birth": "1988-07-14",
            "phone_number": "3105556666",
            "address": "Calle 6 #6-6",
            # Falta 'eps'
        }

        serializer = PatientRegistrationSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("eps", serializer.errors)

    def test_missing_required_identity_document(self):
        """Test: Validación - Documento de identidad es requerido"""
        data = {
            "user": {
                "email": "sin_documento@test.com",
                "password": "SecurePassword123!",
                "nombre": "Fernando",
                "apellido": "Rodríguez",
            },
            # Falta 'identity_document'
            "document_type": Patient.DocumentType.CC,
            "date_birth": "1991-11-23",
            "phone_number": "3105557777",
            "address": "Calle 7 #7-7",
            "eps": self.eps.id,
        }

        serializer = PatientRegistrationSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("identity_document", serializer.errors)

    def test_duplicate_email_validation(self):
        """Test: Validación - Email duplicado causa error en save()"""
        from django.db import IntegrityError
        
        # Crear primer usuario
        User.objects.create_user(
            email="existente@test.com",
            password="Password123!",
            nombre="Primer",
            apellido="Usuario",
            rol=User.Role.PATIENT,
        )

        # Intentar crear paciente con el mismo email
        data = {
            "user": {
                "email": "existente@test.com",
                "password": "SecurePassword123!",
                "nombre": "Segundo",
                "apellido": "Usuario",
            },
            "identity_document": "77777777",
            "document_type": Patient.DocumentType.CC,
            "date_birth": "1993-01-15",
            "phone_number": "3105558888",
            "address": "Calle 8 #8-8",
            "eps": self.eps.id,
        }

        serializer = PatientRegistrationSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        
        # El error ocurre durante save() por constraint de BD
        with self.assertRaises(IntegrityError):
            serializer.save()

    def test_duplicate_identity_document_validation(self):
        """Test: Validación - Documento de identidad duplicado"""
        # Crear primer paciente
        user1 = User.objects.create_user(
            email="usuario1@test.com",
            password="Password123!",
            nombre="Usuario",
            apellido="Uno",
            rol=User.Role.PATIENT,
        )
        Patient.objects.create(
            user=user1,
            identity_document="88888888",
            document_type=Patient.DocumentType.CC,
            date_birth=date(1990, 1, 1),
            phone_number="3105550011",
            address="Carrera 1 #1-1",
            eps=self.eps,
        )

        # Intentar crear segundo paciente con el mismo documento
        data = {
            "user": {
                "email": "usuario2@test.com",
                "password": "SecurePassword123!",
                "nombre": "Usuario",
                "apellido": "Dos",
            },
            "identity_document": "88888888",  # Documento duplicado
            "document_type": Patient.DocumentType.CC,
            "date_birth": "1992-04-22",
            "phone_number": "3105552233",
            "address": "Carrera 2 #2-2",
            "eps": self.eps.id,
        }

        serializer = PatientRegistrationSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("identity_document", serializer.errors)

    def test_to_representation_format(self):
        """Test: Formato correcto de respuesta (to_representation)"""
        # Crear un paciente válido
        user = User.objects.create_user(
            email="respuesta@test.com",
            password="Password123!",
            nombre="Respuesta",
            apellido="Test",
            rol=User.Role.PATIENT,
        )
        patient = Patient.objects.create(
            user=user,
            identity_document="99999999",
            document_type=Patient.DocumentType.CC,
            date_birth=date(1995, 8, 25),
            phone_number="3015559999",
            address="Calle 9 #9-9",
            eps=self.eps,
        )

        serializer = PatientRegistrationSerializer(instance=patient)
        data = serializer.data

        # Verificar estructura de respuesta
        self.assertIn("id", data)
        self.assertIn("user", data)
        self.assertIn("identity_document", data)
        self.assertIn("document_type", data)
        self.assertIn("date_birth", data)
        self.assertIn("phone_number", data)
        self.assertIn("address", data)
        self.assertIn("eps", data)

        # Verificar datos anidados
        self.assertEqual(data["user"]["email"], "respuesta@test.com")
        self.assertEqual(data["user"]["nombre"], "Respuesta")
        self.assertEqual(data["user"]["apellido"], "Test")
        self.assertEqual(data["identity_document"], "99999999")
        self.assertEqual(data["eps"]["id"], self.eps.id)
        self.assertEqual(data["eps"]["name"], self.eps.name)

    def test_atomic_transaction_on_save(self):
        """Test: Transacción atómica al guardar"""
        eps_activa = EPS.objects.create(
            name="FAMISANAR",
            code="FAM001",
            active=True,
        )

        data_valido = {
            "user": {
                "email": "atomico@test.com",
                "password": "SecurePassword123!",
                "nombre": "Atómico",
                "apellido": "Test",
            },
            "identity_document": "11223344",
            "document_type": Patient.DocumentType.CC,
            "date_birth": "1994-05-12",
            "phone_number": "3125556677",
            "address": "Calle Principal #10",
            "eps": eps_activa.id,
        }

        # La transacción debe completar exitosamente
        serializer = PatientRegistrationSerializer(data=data_valido)
        self.assertTrue(serializer.is_valid(), serializer.errors)

        patient = serializer.save()
        self.assertIsNotNone(patient)

        # Verificar que tanto usuario como paciente existen
        self.assertTrue(
            User.objects.filter(email="atomico@test.com").exists()
        )
        self.assertTrue(
            Patient.objects.filter(identity_document="11223344").exists()
        )

    def test_all_document_types(self):
        """Test: Todos los tipos de documento son válidos"""
        document_types = [
            Patient.DocumentType.CC,
            Patient.DocumentType.TI,
            Patient.DocumentType.CE,
            Patient.DocumentType.PAS,
        ]

        for idx, doc_type in enumerate(document_types):
            data = {
                "user": {
                    "email": f"doc_type_{idx}@test.com",
                    "password": "SecurePassword123!",
                    "nombre": "Test",
                    "apellido": "DocType",
                },
                "identity_document": f"5555555{idx}",
                "document_type": doc_type,
                "date_birth": "1990-01-01",
                "phone_number": f"300555000{idx}",
                "address": f"Calle {idx} #12-34",
                "eps": self.eps.id,
            }

            serializer = PatientRegistrationSerializer(data=data)
            self.assertTrue(serializer.is_valid(), 
                          f"Validación falló para tipo: {doc_type} - Errores: {serializer.errors}")

            patient = serializer.save()
            self.assertEqual(patient.document_type, doc_type)


class PatientMeViewTests(APITestCase):
    """Pruebas para el endpoint GET/PATCH /api/patients/me/"""

    password = "ClaveSegura123*"

    def setUp(self):
        self.url = reverse("patient-me")
        self.eps = EPS.objects.create(name="SURA", code="SURA001", active=True)

        self.patient_user = User.objects.create_user(
            email="paciente@test.com",
            password=self.password,
            nombre="Juan",
            apellido="Garcia",
            rol=User.Role.PATIENT,
        )
        self.patient = Patient.objects.create(
            user=self.patient_user,
            identity_document="12345678",
            document_type=Patient.DocumentType.CC,
            date_birth=date(1990, 5, 15),
            phone_number="3015551234",
            address="Calle 1 #2-3",
            eps=self.eps,
        )

    def test_requires_authentication(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_non_patient_receives_403(self):
        admin_user = User.objects.create_user(
            email="admin@test.com",
            password=self.password,
            nombre="Admin",
            apellido="Sistema",
            rol=User.Role.ADMINISTRATIVE,
        )
        self.client.force_authenticate(user=admin_user)

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_get_returns_patient_profile(self):
        self.client.force_authenticate(user=self.patient_user)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["full_name"], "Juan Garcia")
        self.assertEqual(response.data["identity_document"], "12345678")
        self.assertEqual(response.data["eps"], "SURA")
        self.assertEqual(response.data["email"], "paciente@test.com")
        self.assertEqual(response.data["phone_number"], "3015551234")

    def test_patch_updates_email_and_phone(self):
        self.client.force_authenticate(user=self.patient_user)

        response = self.client.patch(
            self.url,
            {"email": "nuevo@test.com", "phone_number": "3009998888"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["message"], "Perfil actualizado correctamente")

        self.patient_user.refresh_from_db()
        self.patient.refresh_from_db()
        self.assertEqual(self.patient_user.email, "nuevo@test.com")
        self.assertEqual(self.patient.phone_number, "3009998888")

    def test_patch_duplicate_email_returns_400(self):
        User.objects.create_user(
            email="otro@test.com",
            password=self.password,
            nombre="Otro",
            apellido="Usuario",
            rol=User.Role.PATIENT,
        )
        self.client.force_authenticate(user=self.patient_user)

        response = self.client.patch(self.url, {"email": "otro@test.com"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_patch_non_numeric_phone_returns_400(self):
        self.client.force_authenticate(user=self.patient_user)

        response = self.client.patch(
            self.url, {"phone_number": "300-abc-1234"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_patch_rejects_identity_document_and_eps_changes(self):
        self.client.force_authenticate(user=self.patient_user)

        response = self.client.patch(
            self.url,
            {"identity_document": "99999999", "eps": self.eps.id},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        self.patient.refresh_from_db()
        self.assertEqual(self.patient.identity_document, "12345678")


class PatientStatusViewTests(APITestCase):
    """Pruebas para los endpoints POST /api/patients/<id>/deactivate/ y /activate/"""

    password = "ClaveSegura123*"

    def setUp(self):
        self.eps = EPS.objects.create(name="SURA", code="SURA001", active=True)

        self.patient_user = User.objects.create_user(
            email="paciente@test.com",
            password=self.password,
            nombre="Juan",
            apellido="Garcia",
            rol=User.Role.PATIENT,
        )
        self.patient = Patient.objects.create(
            user=self.patient_user,
            identity_document="12345678",
            document_type=Patient.DocumentType.CC,
            date_birth=date(1990, 5, 15),
            phone_number="3015551234",
            address="Calle 1 #2-3",
            eps=self.eps,
        )

        self.admin_user = User.objects.create_user(
            email="admin@test.com",
            password=self.password,
            nombre="Admin",
            apellido="Sistema",
            rol=User.Role.ADMINISTRATIVE,
        )

        self.deactivate_url = reverse("patient-deactivate", args=[self.patient.pk])
        self.activate_url = reverse("patient-activate", args=[self.patient.pk])

    def test_admin_can_deactivate_patient(self):
        self.client.force_authenticate(user=self.admin_user)

        response = self.client.post(self.deactivate_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.patient_user.refresh_from_db()
        self.assertFalse(self.patient_user.is_active)

    def test_admin_can_reactivate_patient(self):
        self.patient_user.is_active = False
        self.patient_user.save(update_fields=["is_active"])
        self.client.force_authenticate(user=self.admin_user)

        response = self.client.post(self.activate_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.patient_user.refresh_from_db()
        self.assertTrue(self.patient_user.is_active)

    def test_patient_receives_403(self):
        self.client.force_authenticate(user=self.patient_user)

        response = self.client.post(self.deactivate_url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_doctor_receives_403(self):
        doctor_user = User.objects.create_user(
            email="doctor@test.com",
            password=self.password,
            nombre="Doc",
            apellido="Tor",
            rol=User.Role.DOCTOR,
        )
        self.client.force_authenticate(user=doctor_user)

        response = self.client.post(self.deactivate_url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_unauthenticated_user_receives_401(self):
        response = self.client.post(self.deactivate_url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_nonexistent_patient_receives_404(self):
        self.client.force_authenticate(user=self.admin_user)

        url = reverse("patient-deactivate", args=[999999])
        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_deactivate_twice_receives_400(self):
        self.client.force_authenticate(user=self.admin_user)

        first_response = self.client.post(self.deactivate_url)
        second_response = self.client.post(self.deactivate_url)

        self.assertEqual(first_response.status_code, status.HTTP_200_OK)
        self.assertEqual(second_response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_deactivated_patient_cannot_login(self):
        self.client.force_authenticate(user=self.admin_user)
        self.client.post(self.deactivate_url)
        self.client.force_authenticate(user=None)

        login_url = reverse("auth-login")
        response = self.client.post(
            login_url,
            {"email": "paciente@test.com", "password": self.password},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_deactivated_patient_jwt_token_rejected_on_protected_endpoint(self):
        # Emite un access token real (sin force_authenticate) mientras el paciente está activo.
        refresh = RefreshToken.for_user(self.patient_user)
        access_token = str(refresh.access_token)

        self.client.force_authenticate(user=self.admin_user)
        response = self.client.post(self.deactivate_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        anonymous_client = APIClient()
        anonymous_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")

        me_response = anonymous_client.get(reverse("patient-me"))

        self.assertEqual(me_response.status_code, status.HTTP_401_UNAUTHORIZED)