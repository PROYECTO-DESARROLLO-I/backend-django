from datetime import date, time, timedelta

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from availability.models import DoctorAvailability
from doctor.models import Doctor, DoctorSpecialty
from headquarters.models import Headquarters
from specialties.models import Specialty
from user.models import User


class SpecialtyListTests(APITestCase):
    def setUp(self):
        self.url = reverse("specialty-list")
        self.password = "ClaveSegura123*"

        self.patient_user = User.objects.create_user(
            email="paciente@test.com",
            password=self.password,
            nombre="Maria",
            apellido="Lopez",
            rol=User.Role.PATIENT,
        )

        doctor_user = User.objects.create_user(
            email="medico@test.com",
            password=self.password,
            nombre="Carlos",
            apellido="Perez",
            rol=User.Role.DOCTOR,
        )
        self.headquarters = Headquarters.objects.create(name="Sede Central", active=True)
        self.specialty = Specialty.objects.create(name="Medicina General", active=True)
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

    def test_returns_active_specialties_that_have_available_doctors(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["name"], "Medicina General")

    def test_includes_available_doctors_count(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data[0]["available_doctors_count"], 1)

    def test_count_increases_when_second_doctor_joins_specialty(self):
        doctor_user2 = User.objects.create_user(
            email="medico2@test.com",
            password=self.password,
            nombre="Ana",
            apellido="Ruiz",
            rol=User.Role.DOCTOR,
        )
        doctor2 = Doctor.objects.create(
            user=doctor_user2, identity_document="111222333", active=True
        )
        DoctorSpecialty.objects.create(doctor=doctor2, specialty=self.specialty)
        tomorrow_weekday = (date.today() + timedelta(days=1)).weekday()
        DoctorAvailability.objects.create(
            doctor=doctor2,
            specialty=self.specialty,
            weekday=tomorrow_weekday,
            start_time=time(8, 0),
            end_time=time(17, 0),
            appointment_duration=30,
            active=True,
        )

        response = self.client.get(self.url)

        self.assertEqual(response.data[0]["available_doctors_count"], 2)

    def test_excludes_inactive_specialties(self):
        Specialty.objects.create(name="Especialidad Inactiva", active=False)

        response = self.client.get(self.url)

        names = [s["name"] for s in response.data]
        self.assertNotIn("Especialidad Inactiva", names)

    def test_excludes_specialties_without_doctors_available_in_next_30_days(self):
        Specialty.objects.create(name="Sin medicos", active=True)

        response = self.client.get(self.url)

        names = [s["name"] for s in response.data]
        self.assertNotIn("Sin medicos", names)

    def test_excludes_specialties_whose_only_availability_is_inactive(self):
        specialty2 = Specialty.objects.create(name="Solo inactiva", active=True)
        doctor_user2 = User.objects.create_user(
            email="medico3@test.com",
            password=self.password,
            nombre="Pedro",
            apellido="Gil",
            rol=User.Role.DOCTOR,
        )
        doctor2 = Doctor.objects.create(
            user=doctor_user2, identity_document="555666777", active=True
        )
        DoctorSpecialty.objects.create(doctor=doctor2, specialty=specialty2)
        DoctorAvailability.objects.create(
            doctor=doctor2,
            specialty=specialty2,
            weekday=0,
            start_time=time(8, 0),
            end_time=time(17, 0),
            appointment_duration=30,
            active=False,
        )

        response = self.client.get(self.url)

        names = [s["name"] for s in response.data]
        self.assertNotIn("Solo inactiva", names)

    def test_requires_authentication(self):
        self.client.force_authenticate(user=None)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
