from datetime import date, time, timedelta
from unittest.mock import patch

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from availability.models import DoctorAvailability, ScheduleException
from doctor.models import Doctor, DoctorSpecialty
from headquarters.models import Headquarters
from specialties.models import Specialty
from user.models import User


class DoctorListTests(APITestCase):
    def setUp(self):
        self.url = reverse("doctor-list")
        self.password = "ClaveSegura123*"

        self.patient_user = User.objects.create_user(
            email="paciente@test.com",
            password=self.password,
            nombre="Maria",
            apellido="Lopez",
            rol=User.Role.PATIENT,
        )
        self.specialty = Specialty.objects.create(name="Medicina General", active=True)
        self.headquarters = Headquarters.objects.create(name="Sede Central", active=True)

        doctor_user = User.objects.create_user(
            email="medico@test.com",
            password=self.password,
            nombre="Carlos",
            apellido="Perez",
            rol=User.Role.DOCTOR,
        )
        self.doctor = Doctor.objects.create(
            user=doctor_user,
            identity_document="987654321",
            active=True,
        )
        DoctorSpecialty.objects.create(doctor=self.doctor, specialty=self.specialty)

        tomorrow_weekday = (date.today() + timedelta(days=1)).weekday()
        DoctorAvailability.objects.create(
            doctor=self.doctor,
            specialty=self.specialty,
            headquarters=self.headquarters,
            weekday=tomorrow_weekday,
            start_time=time(8, 0),
            end_time=time(17, 0),
            appointment_duration=30,
            active=True,
        )

        self.client.force_authenticate(user=self.patient_user)

    def test_returns_doctors_for_requested_specialty(self):
        response = self.client.get(self.url, {"specialty": self.specialty.id})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_doctor_response_includes_full_name_specialties_and_next_date(self):
        response = self.client.get(self.url, {"specialty": self.specialty.id})

        doctor_data = response.data[0]
        self.assertEqual(doctor_data["full_name"], "Carlos Perez")
        self.assertIn("specialties", doctor_data)
        self.assertIsNotNone(doctor_data["next_available_date"])

    def test_next_available_date_is_within_next_30_days(self):
        response = self.client.get(self.url, {"specialty": self.specialty.id})

        next_date_str = response.data[0]["next_available_date"]
        next_date = date.fromisoformat(next_date_str)
        self.assertGreater(next_date, date.today())
        self.assertLessEqual(next_date, date.today() + timedelta(days=30))

    def test_doctor_specialties_list_includes_name_and_id(self):
        response = self.client.get(self.url, {"specialty": self.specialty.id})

        specialties = response.data[0]["specialties"]
        self.assertEqual(len(specialties), 1)
        self.assertEqual(specialties[0]["name"], "Medicina General")
        self.assertIn("id", specialties[0])

    def test_excludes_doctors_without_availability_in_next_30_days(self):
        doctor_user2 = User.objects.create_user(
            email="medico2@test.com",
            password=self.password,
            nombre="Sin",
            apellido="Disponibilidad",
            rol=User.Role.DOCTOR,
        )
        doctor2 = Doctor.objects.create(
            user=doctor_user2, identity_document="000000001", active=True
        )
        DoctorSpecialty.objects.create(doctor=doctor2, specialty=self.specialty)

        response = self.client.get(self.url, {"specialty": self.specialty.id})

        full_names = [d["full_name"] for d in response.data]
        self.assertNotIn("Sin Disponibilidad", full_names)

    def test_excludes_doctors_whose_available_days_are_all_blocked_by_exceptions(self):
        tomorrow = date.today() + timedelta(days=1)
        doctor_user2 = User.objects.create_user(
            email="medico3@test.com",
            password=self.password,
            nombre="Todo",
            apellido="Bloqueado",
            rol=User.Role.DOCTOR,
        )
        doctor2 = Doctor.objects.create(
            user=doctor_user2, identity_document="000000002", active=True
        )
        DoctorSpecialty.objects.create(doctor=doctor2, specialty=self.specialty)
        DoctorAvailability.objects.create(
            doctor=doctor2,
            specialty=self.specialty,
            weekday=tomorrow.weekday(),
            start_time=time(8, 0),
            end_time=time(17, 0),
            appointment_duration=30,
            active=True,
        )
        for i in range(1, 31):
            day = date.today() + timedelta(days=i)
            if day.weekday() == tomorrow.weekday():
                ScheduleException.objects.create(
                    doctor=doctor2,
                    date=day,
                    type=ScheduleException.ExceptionType.BLOCK,
                )

        response = self.client.get(self.url, {"specialty": self.specialty.id})

        full_names = [d["full_name"] for d in response.data]
        self.assertNotIn("Todo Bloqueado", full_names)

    def test_does_not_return_doctors_from_other_specialties(self):
        other_specialty = Specialty.objects.create(name="Cardiologia", active=True)

        response = self.client.get(self.url, {"specialty": other_specialty.id})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0)

    def test_returns_400_when_specialty_param_is_missing(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_requires_authentication(self):
        self.client.force_authenticate(user=None)

        response = self.client.get(self.url, {"specialty": self.specialty.id})

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class DoctorCreateTests(APITestCase):
    password = "ClaveSegura123*"

    def setUp(self):
        self.url = reverse("doctor-list")
        self.specialty1 = Specialty.objects.create(name="Medicina General", active=True)
        self.specialty2 = Specialty.objects.create(name="Cardiología", active=True)

        self.admin_user = User.objects.create_user(
            email="admin@test.com",
            password=self.password,
            nombre="Admin",
            apellido="Sistema",
            rol=User.Role.ADMINISTRATIVE,
        )
        self.client.force_authenticate(user=self.admin_user)

    def base_payload(self, **overrides):
        payload = {
            "nombre": "Ana",
            "apellido": "Rios",
            "email": "ana.rios@hospital.com",
            "password": self.password,
            "identity_document": "11223344",
            "register_number": "RM-001",
            "phone_number": "3001234567",
            "academic_information": "Médica graduada de la Universidad Nacional.",
            "specialty_ids": [self.specialty1.id],
        }
        payload.update(overrides)
        return payload

    @patch("doctor.views.send_doctor_welcome")
    def test_admin_can_create_doctor(self, mock_email):
        response = self.client.post(self.url, self.base_payload(), format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    @patch("doctor.views.send_doctor_welcome")
    def test_response_includes_expected_fields(self, mock_email):
        response = self.client.post(self.url, self.base_payload(), format="json")

        self.assertIn("id", response.data)
        self.assertIn("nombre", response.data)
        self.assertIn("apellido", response.data)
        self.assertIn("email", response.data)
        self.assertIn("identity_document", response.data)
        self.assertIn("register_number", response.data)
        self.assertIn("specialties", response.data)
        self.assertIn("active", response.data)
        self.assertEqual(response.data["nombre"], "Ana")
        self.assertEqual(response.data["email"], "ana.rios@hospital.com")

    @patch("doctor.views.send_doctor_welcome")
    def test_creates_user_with_doctor_role(self, mock_email):
        self.client.post(self.url, self.base_payload(), format="json")

        user = User.objects.get(email="ana.rios@hospital.com")
        self.assertEqual(user.rol, User.Role.DOCTOR)

    @patch("doctor.views.send_doctor_welcome")
    def test_password_is_stored_hashed(self, mock_email):
        self.client.post(self.url, self.base_payload(), format="json")

        user = User.objects.get(email="ana.rios@hospital.com")
        self.assertNotEqual(user.password, self.password)
        self.assertTrue(user.check_password(self.password))

    @patch("doctor.views.send_doctor_welcome")
    def test_specialties_are_linked_to_doctor(self, mock_email):
        payload = self.base_payload(specialty_ids=[self.specialty1.id, self.specialty2.id])
        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(response.data["specialties"]), 2)
        specialty_names = [s["name"] for s in response.data["specialties"]]
        self.assertIn("Medicina General", specialty_names)
        self.assertIn("Cardiología", specialty_names)

    @patch("doctor.views.send_doctor_welcome")
    def test_sends_welcome_email_on_successful_creation(self, mock_email):
        self.client.post(self.url, self.base_payload(), format="json")

        mock_email.assert_called_once()
        doctor_arg = mock_email.call_args[0][0]
        self.assertEqual(doctor_arg.user.email, "ana.rios@hospital.com")

    @patch("doctor.views.send_doctor_welcome")
    def test_superadmin_can_also_create_doctor(self, mock_email):
        superadmin = User.objects.create_user(
            email="superadmin@test.com",
            password=self.password,
            nombre="Super",
            apellido="Admin",
            rol=User.Role.SUPERADMIN,
        )
        self.client.force_authenticate(user=superadmin)

        response = self.client.post(self.url, self.base_payload(), format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_patient_cannot_create_doctor(self):
        patient_user = User.objects.create_user(
            email="paciente@test.com",
            password=self.password,
            nombre="Paciente",
            apellido="Test",
            rol=User.Role.PATIENT,
        )
        self.client.force_authenticate(user=patient_user)

        response = self.client.post(self.url, self.base_payload(), format="json")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_doctor_user_cannot_create_another_doctor(self):
        doctor_user = User.objects.create_user(
            email="medico@test.com",
            password=self.password,
            nombre="Médico",
            apellido="Test",
            rol=User.Role.DOCTOR,
        )
        self.client.force_authenticate(user=doctor_user)

        response = self.client.post(self.url, self.base_payload(), format="json")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_requires_authentication(self):
        self.client.force_authenticate(user=None)

        response = self.client.post(self.url, self.base_payload(), format="json")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_rejects_duplicate_email(self):
        User.objects.create_user(
            email="ana.rios@hospital.com",
            password=self.password,
            nombre="Otro",
            apellido="Usuario",
            rol=User.Role.DOCTOR,
        )

        response = self.client.post(self.url, self.base_payload(), format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data)

    @patch("doctor.views.send_doctor_welcome")
    def test_rejects_duplicate_identity_document(self, mock_email):
        self.client.post(self.url, self.base_payload(), format="json")

        payload = self.base_payload(email="otro@hospital.com", register_number="RM-002")
        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("identity_document", response.data)

    @patch("doctor.views.send_doctor_welcome")
    def test_rejects_duplicate_register_number(self, mock_email):
        self.client.post(self.url, self.base_payload(), format="json")

        payload = self.base_payload(email="otro@hospital.com", identity_document="99887766")
        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("register_number", response.data)

    def test_rejects_nonexistent_specialty(self):
        payload = self.base_payload(specialty_ids=[99999])

        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("specialty_ids", response.data)

    def test_rejects_inactive_specialty(self):
        inactive = Specialty.objects.create(name="Inactiva", active=False)
        payload = self.base_payload(specialty_ids=[inactive.id])

        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("specialty_ids", response.data)

    def test_rejects_empty_specialty_list(self):
        payload = self.base_payload(specialty_ids=[])

        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("specialty_ids", response.data)

    def test_returns_400_when_required_fields_are_missing(self):
        response = self.client.post(self.url, {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        for field in ["nombre", "apellido", "email", "password", "identity_document", "register_number", "specialty_ids"]:
            self.assertIn(field, response.data)

    def test_rejects_password_shorter_than_8_chars(self):
        payload = self.base_payload(password="corta1")

        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("password", response.data)

    @patch("doctor.views.send_doctor_welcome")
    def test_deduplicates_repeated_specialty_ids(self, mock_email):
        payload = self.base_payload(specialty_ids=[self.specialty1.id, self.specialty1.id])
        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(response.data["specialties"]), 1)
