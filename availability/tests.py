from datetime import date, datetime, time, timedelta

from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from appointment.models import Appointment
from availability.models import DoctorAvailability, ScheduleException
from doctor.models import Doctor, DoctorSpecialty
from eps.models import EPS
from headquarters.models import Headquarters
from patient.models import Patient
from specialties.models import Specialty
from user.models import User


class AvailableSlotsTests(APITestCase):
    def setUp(self):
        self.url = reverse("availability-slots")
        self.password = "ClaveSegura123*"

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
            date_birth=date(1990, 1, 1),
            eps=eps,
            date_birth="2000-01-01",
        )

        doctor_user = User.objects.create_user(
            email="medico@test.com",
            password=self.password,
            nombre="Carlos",
            apellido="Perez",
            rol=User.Role.DOCTOR,
        )
        self.specialty = Specialty.objects.create(name="Medicina General", active=True)
        self.headquarters = Headquarters.objects.create(name="Sede Central", active=True)
        self.doctor = Doctor.objects.create(
            user=doctor_user,
            identity_document="987654321",
            active=True,
        )
        DoctorSpecialty.objects.create(doctor=self.doctor, specialty=self.specialty)

        # Availability for all weekdays so tests always find matching days
        for weekday in range(7):
            DoctorAvailability.objects.create(
                doctor=self.doctor,
                specialty=self.specialty,
                headquarters=self.headquarters,
                weekday=weekday,
                start_time=time(8, 0),
                end_time=time(10, 0),
                appointment_duration=30,
                active=True,
            )

        # Use a date 2 days from now to avoid timezone edge cases
        self.test_date = date.today() + timedelta(days=2)

        self.client.force_authenticate(user=patient_user)

    def test_returns_slots_with_expected_fields(self):
        response = self.client.get(self.url, {
            "doctor": self.doctor.id,
            "specialty": self.specialty.id,
            "date": self.test_date.isoformat(),
        })

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("slots", response.data)
        self.assertGreater(len(response.data["slots"]), 0)
        slot = response.data["slots"][0]
        self.assertIn("date", slot)
        self.assertIn("start_time", slot)
        self.assertIn("end_time", slot)
        self.assertIn("duration_minutes", slot)
        self.assertIn("headquarters_id", slot)
        self.assertIn("headquarters_name", slot)

    def test_default_view_is_weekly(self):
        response = self.client.get(self.url, {
            "doctor": self.doctor.id,
            "specialty": self.specialty.id,
            "date": self.test_date.isoformat(),
        })

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["view"], "week")
        slot_dates = {s["date"] for s in response.data["slots"]}
        # All slots must fall within a 7-day window
        end_date = self.test_date + timedelta(days=6)
        for d in slot_dates:
            self.assertLessEqual(date.fromisoformat(d), end_date)

    def test_month_view_covers_30_days(self):
        response = self.client.get(self.url, {
            "doctor": self.doctor.id,
            "specialty": self.specialty.id,
            "date": self.test_date.isoformat(),
            "view": "month",
        })

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["view"], "month")
        slot_dates = {s["date"] for s in response.data["slots"]}
        end_date = self.test_date + timedelta(days=29)
        # The month view should produce slots across multiple weeks
        self.assertGreater(len(slot_dates), 1)
        for d in slot_dates:
            self.assertLessEqual(date.fromisoformat(d), end_date)

    def test_slots_include_correct_duration_and_headquarters(self):
        response = self.client.get(self.url, {
            "doctor": self.doctor.id,
            "specialty": self.specialty.id,
            "date": self.test_date.isoformat(),
        })

        slot = response.data["slots"][0]
        self.assertEqual(slot["duration_minutes"], 30)
        self.assertEqual(slot["headquarters_id"], self.headquarters.id)
        self.assertEqual(slot["headquarters_name"], "Sede Central")

    def test_excludes_days_blocked_by_schedule_exception(self):
        ScheduleException.objects.create(
            doctor=self.doctor,
            date=self.test_date,
            type=ScheduleException.ExceptionType.BLOCK,
        )

        response = self.client.get(self.url, {
            "doctor": self.doctor.id,
            "specialty": self.specialty.id,
            "date": self.test_date.isoformat(),
        })

        slot_dates = {s["date"] for s in response.data["slots"]}
        self.assertNotIn(self.test_date.isoformat(), slot_dates)

    def test_excludes_already_booked_slots(self):
        admin_user = User.objects.create_user(
            email="admin@test.com",
            password=self.password,
            nombre="Admin",
            apellido="Sistema",
            rol=User.Role.ADMINISTRATIVE,
        )
        booked_at = timezone.make_aware(datetime.combine(self.test_date, time(8, 0)))
        Appointment.objects.create(
            patient=self.patient,
            doctor=self.doctor,
            specialty=self.specialty,
            headquarters=self.headquarters,
            scheduled_at=booked_at,
            duration_minutes=30,
            status=Appointment.Status.CONFIRMED,
            created_by=admin_user,
        )

        response = self.client.get(self.url, {
            "doctor": self.doctor.id,
            "specialty": self.specialty.id,
            "date": self.test_date.isoformat(),
        })

        booked_slots = [
            s for s in response.data["slots"]
            if s["date"] == self.test_date.isoformat() and s["start_time"] == "08:00:00"
        ]
        self.assertEqual(len(booked_slots), 0)

    def test_still_shows_remaining_slots_when_one_is_booked(self):
        admin_user = User.objects.create_user(
            email="admin2@test.com",
            password=self.password,
            nombre="Admin",
            apellido="Two",
            rol=User.Role.ADMINISTRATIVE,
        )
        booked_at = timezone.make_aware(datetime.combine(self.test_date, time(8, 0)))
        Appointment.objects.create(
            patient=self.patient,
            doctor=self.doctor,
            specialty=self.specialty,
            headquarters=self.headquarters,
            scheduled_at=booked_at,
            duration_minutes=30,
            status=Appointment.Status.CONFIRMED,
            created_by=admin_user,
        )

        response = self.client.get(self.url, {
            "doctor": self.doctor.id,
            "specialty": self.specialty.id,
            "date": self.test_date.isoformat(),
        })

        day_slots = [s for s in response.data["slots"] if s["date"] == self.test_date.isoformat()]
        # 08:00 slot gone but 08:30 and 09:00 and 09:30 should remain
        start_times = [s["start_time"] for s in day_slots]
        self.assertIn("08:30:00", start_times)
        self.assertNotIn("08:00:00", start_times)

    def test_returns_empty_slots_when_doctor_has_no_availability_for_specialty(self):
        other_specialty = Specialty.objects.create(name="Cardiologia", active=True)

        response = self.client.get(self.url, {
            "doctor": self.doctor.id,
            "specialty": other_specialty.id,
            "date": self.test_date.isoformat(),
        })

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["slots"]), 0)

    def test_returns_400_when_doctor_or_specialty_is_missing(self):
        response = self.client.get(self.url, {"specialty": self.specialty.id})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        response = self.client.get(self.url, {"doctor": self.doctor.id})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_returns_400_for_invalid_date_format(self):
        response = self.client.get(self.url, {
            "doctor": self.doctor.id,
            "specialty": self.specialty.id,
            "date": "no-es-fecha",
        })

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_slot_response_includes_new_hq14_fields(self):
        response = self.client.get(self.url, {
            "doctor": self.doctor.id,
            "specialty": self.specialty.id,
            "date": self.test_date.isoformat(),
        })

        slot = response.data["slots"][0]
        self.assertIn("doctor_id", slot)
        self.assertIn("doctor_name", slot)
        self.assertIn("headquarters_address", slot)
        self.assertIn("consulting_room", slot)

    def test_requires_authentication(self):
        self.client.force_authenticate(user=None)

        response = self.client.get(self.url, {
            "doctor": self.doctor.id,
            "specialty": self.specialty.id,
        })

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class AvailableSlotsByHeadquartersTests(APITestCase):
    """HU14: slots filtered by specialty + headquarters."""

    password = "ClaveSegura123*"

    def setUp(self):
        self.url = reverse("availability-slots")

        patient_user = User.objects.create_user(
            email="paciente@test.com",
            password=self.password,
            nombre="Maria",
            apellido="Lopez",
            rol=User.Role.PATIENT,
        )
        eps = EPS.objects.create(name="EPS Test", code="EPS001", active=True)
        Patient.objects.create(
            user=patient_user,
            identity_document="123456789",
            document_type=Patient.DocumentType.CC,
            date_birth=date(1990, 1, 1),
            phone_number="+573001234567",
            address="Calle 1 # 2-3",
            eps=eps,
        )

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

        for weekday in range(7):
            DoctorAvailability.objects.create(
                doctor=self.doctor,
                specialty=self.specialty,
                headquarters=self.hq,
                weekday=weekday,
                start_time=time(8, 0),
                end_time=time(10, 0),
                appointment_duration=30,
                consulting_room="Consultorio 3",
                active=True,
            )

        self.test_date = date.today() + timedelta(days=2)
        self.client.force_authenticate(user=patient_user)

    def test_returns_slots_for_specialty_and_headquarters(self):
        response = self.client.get(self.url, {
            "specialty": self.specialty.id,
            "headquarters": self.hq.id,
            "date_from": self.test_date.isoformat(),
            "date_to": (self.test_date + timedelta(days=1)).isoformat(),
        })

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("slots", response.data)
        self.assertGreater(len(response.data["slots"]), 0)

    def test_response_includes_headquarters_address_and_consulting_room(self):
        response = self.client.get(self.url, {
            "specialty": self.specialty.id,
            "headquarters": self.hq.id,
            "date_from": self.test_date.isoformat(),
            "date_to": self.test_date.isoformat(),
        })

        slot = response.data["slots"][0]
        self.assertEqual(slot["headquarters_address"], "Calle 100 # 15-20")
        self.assertEqual(slot["consulting_room"], "Consultorio 3")
        self.assertEqual(slot["headquarters_name"], "Sede Norte")

    def test_response_includes_doctor_info_per_slot(self):
        response = self.client.get(self.url, {
            "specialty": self.specialty.id,
            "headquarters": self.hq.id,
            "date_from": self.test_date.isoformat(),
            "date_to": self.test_date.isoformat(),
        })

        slot = response.data["slots"][0]
        self.assertIsNotNone(slot["doctor_id"])
        self.assertIn("Carlos", slot["doctor_name"])

    def test_aggregates_slots_from_multiple_doctors_in_same_sede(self):
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
                headquarters=self.hq,
                weekday=weekday,
                start_time=time(8, 0),
                end_time=time(10, 0),
                appointment_duration=30,
                active=True,
            )

        response = self.client.get(self.url, {
            "specialty": self.specialty.id,
            "headquarters": self.hq.id,
            "date_from": self.test_date.isoformat(),
            "date_to": self.test_date.isoformat(),
        })

        doctor_ids = {s["doctor_id"] for s in response.data["slots"]}
        self.assertIn(self.doctor.id, doctor_ids)
        self.assertIn(doctor2.id, doctor_ids)

    def test_date_range_limits_slots_returned(self):
        single_day = self.test_date
        response = self.client.get(self.url, {
            "specialty": self.specialty.id,
            "headquarters": self.hq.id,
            "date_from": single_day.isoformat(),
            "date_to": single_day.isoformat(),
        })

        dates = {s["date"] for s in response.data["slots"]}
        self.assertEqual(len(dates), 1)
        self.assertIn(single_day.isoformat(), dates)

    def test_returns_400_when_date_to_is_before_date_from(self):
        response = self.client.get(self.url, {
            "specialty": self.specialty.id,
            "headquarters": self.hq.id,
            "date_from": self.test_date.isoformat(),
            "date_to": (self.test_date - timedelta(days=1)).isoformat(),
        })

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_returns_400_when_only_specialty_provided(self):
        response = self.client.get(self.url, {"specialty": self.specialty.id})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_requires_authentication(self):
        self.client.force_authenticate(user=None)

        response = self.client.get(self.url, {
            "specialty": self.specialty.id,
            "headquarters": self.hq.id,
        })

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
