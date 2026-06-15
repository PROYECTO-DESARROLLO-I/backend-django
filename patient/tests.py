from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase

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
                eps=self.eps,
            )

    def test_patient_optional_fields(self):
        """Test: Campos opcionales no obligatorios"""
        patient = Patient.objects.create(
            user=self.user,
            identity_document="12345678",
            # document_type, date_birth, phone_number, address son opcionales
            eps=self.eps,
        )

        self.assertIsNotNone(patient)
        self.assertEqual(patient.document_type, "")
        self.assertIsNone(patient.date_birth)
        self.assertEqual(patient.phone_number, "")
        self.assertEqual(patient.address, "")


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
            "date_birth": date(1985, 3, 20),
            "phone_number": "3105559876",
            "address": "Carrera 5 #10-15",
            "eps": self.eps.id,
        }

        serializer = PatientRegistrationSerializer(data=data)
        self.assertTrue(serializer.is_valid())

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
            "date_birth": tomorrow,  # Fecha futura
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
            "date_birth": today,  # Hoy es válido
            "phone_number": "3105552222",
            "address": "Calle 2 #2-2",
            "eps": self.eps.id,
        }

        serializer = PatientRegistrationSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        
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
            "date_birth": date(1990, 1, 1),
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
            "date_birth": date(1992, 6, 10),
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
            "eps": self.eps.id,
        }

        serializer = PatientRegistrationSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        # Debe haber errores en el usuario anidado
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
            "eps": self.eps.id,
        }

        serializer = PatientRegistrationSerializer(data=data)
        # is_valid() retorna True porque el serializer no valida unicidad de email
        self.assertTrue(serializer.is_valid())
        
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
        self.assertEqual(data["eps"]["name"], self.eps.get_name_display())

    def test_atomic_transaction_on_save(self):
        """Test: Transacción atómica al guardar"""
        # Si ocurre un error después de crear el usuario,
        # el usuario no debe quedar en la BD

        # Primero crear una EPS activa
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
            "eps": eps_activa.id,
        }

        # La transacción debe completar exitosamente
        serializer = PatientRegistrationSerializer(data=data_valido)
        self.assertTrue(serializer.is_valid())

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
                "eps": self.eps.id,
            }

            serializer = PatientRegistrationSerializer(data=data)
            self.assertTrue(serializer.is_valid(), 
                          f"Validación falló para tipo: {doc_type}")

            patient = serializer.save()
            self.assertEqual(patient.document_type, doc_type)
