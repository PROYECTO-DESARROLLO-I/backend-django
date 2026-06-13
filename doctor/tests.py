from datetime import date, time, timedelta

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
        # Block all days with exceptions for the next 30 days
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
