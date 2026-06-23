from datetime import date, datetime, time, timedelta

from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from appointment.models import Appointment
from availability.models import DoctorAvailability
from doctor.models import Doctor, DoctorSpecialty
from eps.models import EPS
from headquarters.models import Headquarters
from patient.models import Patient
from specialties.models import Specialty
from user.models import User


class HeadquartersListSetupMixin:
    password = "ClaveSegura123*"

    def build_scenario(self):
        self.specialty = Specialty.objects.create(name="Medicina General", active=True)
        self.hq = Headquarters.objects.create(
            name="Sede Norte", address="Calle 100 # 15-20", active=True
        )

        doctor_user = User.objects.create_user(
            email="medico@test.com",
            password=self.password,
            nombre="Carlos",
            apellido="Perez",
            rol=User.Role.DOCTOR,
        )
        self.doctor = Doctor.objects.create(
            user=doctor_user, identity_document="987654321", active=True
        )
        DoctorSpecialty.objects.create(doctor=self.doctor, specialty=self.specialty)

        # Availability on all weekdays so tests always find a free slot
        for weekday in range(7):
            DoctorAvailability.objects.create(
                doctor=self.doctor,
                specialty=self.specialty,
                headquarters=self.hq,
                weekday=weekday,
                start_time=time(8, 0),
                end_time=time(10, 0),
                appointment_duration=30,
                active=True,
            )

        patient_user = User.objects.create_user(
            email="paciente@test.com",
            password=self.password,
            nombre="Maria",
            apellido="Lopez",
            rol=User.Role.PATIENT,
        )
        eps = EPS.objects.create(name="EPS Test", code="EPS001", active=True)
        self.patient = Patient.objects.create(
            user=patient_user,
            identity_document="123456789",
            document_type=Patient.DocumentType.CC,
            date_birth=date(1990, 1, 1),
            phone_number="+573001234567",
            address="Calle 1 # 2-3",
            eps=eps,
        )
        self.patient_user = patient_user
        self.client.force_authenticate(user=patient_user)


class HeadquartersListTests(HeadquartersListSetupMixin, APITestCase):
    def setUp(self):
        self.url = reverse("headquarters-list")
        self.build_scenario()

    def test_returns_headquarter_with_free_slots(self):
        response = self.client.get(self.url, {"specialty": self.specialty.id})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["name"], "Sede Norte")

    def test_response_includes_address(self):
        response = self.client.get(self.url, {"specialty": self.specialty.id})

        self.assertEqual(response.data[0]["address"], "Calle 100 # 15-20")

    def test_excludes_headquarter_with_no_doctors_for_specialty(self):
        other_specialty = Specialty.objects.create(name="Cardiologia", active=True)

        response = self.client.get(self.url, {"specialty": other_specialty.id})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0)

    def test_excludes_inactive_headquarter(self):
        self.hq.active = False
        self.hq.save()

        response = self.client.get(self.url, {"specialty": self.specialty.id})

        self.assertEqual(len(response.data), 0)

    def test_excludes_headquarter_when_all_slots_are_booked(self):
        # Fill every slot in the next 30 days
        today = date.today()
        admin_user = User.objects.create_user(
            email="admin@test.com",
            password=self.password,
            nombre="Admin",
            apellido="Sistema",
            rol=User.Role.ADMINISTRATIVE,
        )
        for i in range(1, 31):
            slot_date = today + timedelta(days=i)
            for hour in [8, 8, 9, 9]:  # 08:00, 08:30, 09:00, 09:30
                pass
            # Book all 4 slots for each day
            for minute in [0, 30, 0, 30]:
                for h in [8, 9]:
                    Appointment.objects.create(
                        patient=self.patient,
                        doctor=self.doctor,
                        specialty=self.specialty,
                        headquarters=self.hq,
                        scheduled_at=timezone.make_aware(datetime.combine(slot_date, time(h, minute))),
                        duration_minutes=30,
                        status=Appointment.Status.CONFIRMED,
                        created_by=admin_user,
                    )

        response = self.client.get(self.url, {"specialty": self.specialty.id})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0)

    def test_returns_multiple_headquarters_when_multiple_have_availability(self):
        hq2 = Headquarters.objects.create(name="Sede Sur", address="Carrera 7 # 5-10", active=True)
        doctor_user2 = User.objects.create_user(
            email="medico2@test.com",
            password=self.password,
            nombre="Ana",
            apellido="Rios",
            rol=User.Role.DOCTOR,
        )
        doctor2 = Doctor.objects.create(
            user=doctor_user2, identity_document="111222333", active=True
        )
        DoctorSpecialty.objects.create(doctor=doctor2, specialty=self.specialty)
        for weekday in range(7):
            DoctorAvailability.objects.create(
                doctor=doctor2,
                specialty=self.specialty,
                headquarters=hq2,
                weekday=weekday,
                start_time=time(14, 0),
                end_time=time(16, 0),
                appointment_duration=30,
                active=True,
            )

        response = self.client.get(self.url, {"specialty": self.specialty.id})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)

    def test_returns_400_when_specialty_param_is_missing(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("specialty", response.data)

    def test_requires_authentication(self):
        self.client.force_authenticate(user=None)

        response = self.client.get(self.url, {"specialty": self.specialty.id})

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class DoctorAvailabilityCrossSeatValidationTests(APITestCase):
    """DoctorAvailability.clean() must reject overlapping slots in different sedes."""

    password = "ClaveSegura123*"

    def setUp(self):
        from django.core.exceptions import ValidationError as DjangoValidationError
        self.ValidationError = DjangoValidationError

        specialty = Specialty.objects.create(name="Medicina General", active=True)
        self.hq_a = Headquarters.objects.create(name="Sede A", active=True)
        self.hq_b = Headquarters.objects.create(name="Sede B", active=True)

        doctor_user = User.objects.create_user(
            email="medico@test.com",
            password=self.password,
            nombre="Carlos",
            apellido="Perez",
            rol=User.Role.DOCTOR,
        )
        self.doctor = Doctor.objects.create(
            user=doctor_user, identity_document="987654321", active=True
        )
        DoctorSpecialty.objects.create(doctor=self.doctor, specialty=specialty)
        self.specialty = specialty

        DoctorAvailability.objects.create(
            doctor=self.doctor,
            specialty=self.specialty,
            headquarters=self.hq_a,
            weekday=0,
            start_time=time(8, 0),
            end_time=time(12, 0),
            appointment_duration=30,
            active=True,
        )

    def test_rejects_overlapping_availability_in_different_sede(self):
        conflict = DoctorAvailability(
            doctor=self.doctor,
            specialty=self.specialty,
            headquarters=self.hq_b,
            weekday=0,
            start_time=time(10, 0),
            end_time=time(14, 0),
            appointment_duration=30,
            active=True,
        )

        with self.assertRaises(self.ValidationError):
            conflict.clean()

    def test_allows_non_overlapping_slots_in_different_sedes(self):
        non_conflict = DoctorAvailability(
            doctor=self.doctor,
            specialty=self.specialty,
            headquarters=self.hq_b,
            weekday=0,
            start_time=time(13, 0),
            end_time=time(17, 0),
            appointment_duration=30,
            active=True,
        )

        # Should not raise
        non_conflict.clean()

    def test_allows_same_time_window_in_same_sede(self):
        same_sede = DoctorAvailability(
            doctor=self.doctor,
            specialty=self.specialty,
            headquarters=self.hq_a,
            weekday=0,
            start_time=time(8, 0),
            end_time=time(12, 0),
            appointment_duration=60,
            active=True,
        )

        # Same sede is allowed even if times overlap
        same_sede.clean()

    def test_allows_same_time_on_different_weekday(self):
        different_day = DoctorAvailability(
            doctor=self.doctor,
            specialty=self.specialty,
            headquarters=self.hq_b,
            weekday=1,
            start_time=time(8, 0),
            end_time=time(12, 0),
            appointment_duration=30,
            active=True,
        )

        # Different weekday never conflicts
        different_day.clean()
