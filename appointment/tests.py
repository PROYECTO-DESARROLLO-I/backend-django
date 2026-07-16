from datetime import date, datetime, time, timedelta
from unittest.mock import patch

from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from appointment.models import Appointment, AppointmentHistory
from availability.models import DoctorAvailability, ScheduleException
from doctor.models import Doctor, DoctorSpecialty
from eps.models import EPS
from headquarters.models import Headquarters
from notifications.models import Notification
from patient.models import Patient
from rules.models import EPSAppointmentLimit, EPSBudget, FrequencyRestriction, Period
from specialties.models import Specialty
from user.models import User


def make_aware(d, t):
    return timezone.make_aware(datetime.combine(d, t))


class AppointmentBookingSetupMixin:
    password = "ClaveSegura123*"

    def build_scenario(self):
        self.eps = EPS.objects.create(name="EPS Test", code="EPS001", active=True)

        patient_user = User.objects.create_user(
            email="paciente@test.com",
            password=self.password,
            nombre="Maria",
            apellido="Lopez",
            rol=User.Role.PATIENT,
        )
        self.patient = Patient.objects.create(
            user=patient_user,
            identity_document="123456789",
            document_type=Patient.DocumentType.CC,
            date_birth=date(1990, 1, 1),
            phone_number="+573001234567",
            address="Calle 1 # 2-3",
            eps=self.eps,
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

        for weekday in range(7):
            DoctorAvailability.objects.create(
                doctor=self.doctor,
                specialty=self.specialty,
                headquarters=self.headquarters,
                weekday=weekday,
                start_time=time(8, 0),
                end_time=time(17, 0),
                appointment_duration=30,
                active=True,
            )

        self.test_date = date.today() + timedelta(days=2)
        self.scheduled_at = make_aware(self.test_date, time(9, 0))
        self.patient_user = patient_user
        self.client.force_authenticate(user=patient_user)

    def booking_payload(self, **overrides):
        payload = {
            "doctor_id": self.doctor.id,
            "specialty_id": self.specialty.id,
            "headquarters_id": self.headquarters.id,
            "scheduled_at": self.scheduled_at.isoformat(),
            "consultation_reason": "Control general",
        }
        payload.update(overrides)
        return payload


class AppointmentCreateTests(AppointmentBookingSetupMixin, APITestCase):
    def setUp(self):
        self.url = reverse("appointment-create")
        self.build_scenario()

    @patch("appointment.views.send_appointment_confirmation")
    def test_creates_appointment_with_confirmed_status(self, mock_email):
        response = self.client.post(self.url, self.booking_payload(), format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["status"], Appointment.Status.CONFIRMED)
        self.assertTrue(Appointment.objects.filter(patient=self.patient).exists())

    @patch("appointment.views.send_appointment_confirmation")
    def test_response_includes_expected_appointment_fields(self, mock_email):
        response = self.client.post(self.url, self.booking_payload(), format="json")

        self.assertIn("id", response.data)
        self.assertIn("doctor_name", response.data)
        self.assertIn("specialty_name", response.data)
        self.assertIn("scheduled_at", response.data)
        self.assertIn("duration_minutes", response.data)
        self.assertEqual(response.data["specialty_name"], "Medicina General")
        self.assertIn("Carlos", response.data["doctor_name"])

    @patch("appointment.views.send_appointment_confirmation")
    def test_sends_confirmation_notification(self, mock_email):
        self.client.post(self.url, self.booking_payload(), format="json")

        mock_email.assert_called_once()
        appointment_arg = mock_email.call_args[0][0]
        self.assertEqual(appointment_arg.patient, self.patient)

    @patch("appointment.views.send_appointment_confirmation")
    def test_blocks_slot_so_second_patient_cannot_book_same_time(self, mock_email):
        patient_user2 = User.objects.create_user(
            email="paciente2@test.com",
            password=self.password,
            nombre="Juan",
            apellido="Torres",
            rol=User.Role.PATIENT,
        )
        Patient.objects.create(
            user=patient_user2,
            identity_document="999888777",
            document_type=Patient.DocumentType.CC,
            date_birth=date(1990, 1, 1),
            phone_number="+573001234568",
            address="Calle 1 # 2-3",
            eps=self.eps,
        )

        self.client.post(self.url, self.booking_payload(), format="json")

        self.client.force_authenticate(user=patient_user2)
        response = self.client.post(self.url, self.booking_payload(), format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Esta franja ya no está disponible", str(response.data))

    @patch("appointment.views.send_appointment_confirmation")
    def test_rejects_when_patient_already_has_overlapping_appointment(self, mock_email):
        self.client.post(self.url, self.booking_payload(), format="json")

        specialty2 = Specialty.objects.create(name="Dermatologia", active=True)
        doctor_user2 = User.objects.create_user(
            email="medico2@test.com",
            password=self.password,
            nombre="Ana",
            apellido="Rios",
            rol=User.Role.DOCTOR,
        )
        doctor2 = Doctor.objects.create(
            user=doctor_user2, identity_document="111111111", active=True
        )
        DoctorSpecialty.objects.create(doctor=doctor2, specialty=specialty2)
        for weekday in range(7):
            DoctorAvailability.objects.create(
                doctor=doctor2,
                specialty=specialty2,
                headquarters=self.headquarters,
                weekday=weekday,
                start_time=time(8, 0),
                end_time=time(17, 0),
                appointment_duration=30,
                active=True,
            )

        payload = self.booking_payload(
            doctor_id=doctor2.id,
            specialty_id=specialty2.id,
        )
        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Ya tienes una cita agendada en ese horario.", str(response.data))

    def test_rejects_booking_when_headquarters_does_not_match_availability(self):
        other_hq = Headquarters.objects.create(name="Sede Incorrecta", active=True)

        payload = self.booking_payload(headquarters_id=other_hq.id)
        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("no corresponde a una disponibilidad válida", str(response.data))

    def test_rejects_slot_that_is_not_in_doctor_availability(self):
        payload = self.booking_payload(
            scheduled_at=make_aware(self.test_date, time(23, 0)).isoformat()
        )

        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("no corresponde a una disponibilidad válida", str(response.data))

    def test_rejects_when_doctor_has_schedule_exception_on_that_day(self):
        ScheduleException.objects.create(
            doctor=self.doctor,
            date=self.test_date,
            type=ScheduleException.ExceptionType.VACATION,
        )

        response = self.client.post(self.url, self.booking_payload(), format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("no tiene disponibilidad en esa fecha", str(response.data))

    def test_rejects_when_frequency_restriction_is_exceeded(self):
        FrequencyRestriction.objects.create(
            specialty=self.specialty,
            period=Period.WEEKLY,
            max_appointments_per_patient=1,
        )
        admin_user = User.objects.create_user(
            email="admin@test.com",
            password=self.password,
            nombre="Admin",
            apellido="Sistema",
            rol=User.Role.ADMINISTRATIVE,
        )
        Appointment.objects.create(
            patient=self.patient,
            doctor=self.doctor,
            specialty=self.specialty,
            headquarters=self.headquarters,
            scheduled_at=make_aware(self.test_date, time(8, 0)),
            duration_minutes=30,
            status=Appointment.Status.CONFIRMED,
            created_by=admin_user,
        )

        response = self.client.post(self.url, self.booking_payload(), format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Has alcanzado el límite", str(response.data))

    def test_rejects_when_eps_appointment_limit_is_exceeded(self):
        EPSAppointmentLimit.objects.create(
            eps=self.eps,
            specialty=self.specialty,
            period=Period.MONTHLY,
            max_appointments=1,
            active=True,
        )
        admin_user = User.objects.create_user(
            email="admin@test.com",
            password=self.password,
            nombre="Admin",
            apellido="Sistema",
            rol=User.Role.ADMINISTRATIVE,
        )
        Appointment.objects.create(
            patient=self.patient,
            doctor=self.doctor,
            specialty=self.specialty,
            headquarters=self.headquarters,
            scheduled_at=make_aware(self.test_date, time(8, 0)),
            duration_minutes=30,
            status=Appointment.Status.CONFIRMED,
            created_by=admin_user,
        )

        response = self.client.post(self.url, self.booking_payload(), format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("tope", str(response.data))

    @patch("appointment.views.send_appointment_confirmation")
    def test_eps_limit_blocks_across_different_patients_of_same_eps(self, mock_email):
        EPSAppointmentLimit.objects.create(
            eps=self.eps,
            specialty=self.specialty,
            period=Period.MONTHLY,
            max_appointments=1,
            active=True,
        )
        self.client.post(self.url, self.booking_payload(), format="json")

        patient_user2 = User.objects.create_user(
            email="paciente2@test.com",
            password=self.password,
            nombre="Juan",
            apellido="Torres",
            rol=User.Role.PATIENT,
        )
        Patient.objects.create(
            user=patient_user2,
            identity_document="999888777",
            document_type=Patient.DocumentType.CC,
            date_birth=date(1995, 5, 12),
            phone_number="+573001234568",
            address="Calle 1 # 2-3",
            eps=self.eps,
        )
        self.client.force_authenticate(user=patient_user2)
        response = self.client.post(
            self.url,
            self.booking_payload(scheduled_at=make_aware(self.test_date, time(10, 0)).isoformat()),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("tope", str(response.data))

    @patch("appointment.views.send_appointment_confirmation")
    def test_global_eps_limit_without_specialty_blocks_any_specialty(self, mock_email):
        EPSAppointmentLimit.objects.create(
            eps=self.eps,
            specialty=None,
            period=Period.MONTHLY,
            max_appointments=1,
            active=True,
        )
        self.client.post(self.url, self.booking_payload(), format="json")

        specialty2 = Specialty.objects.create(name="Dermatologia", active=True)
        doctor_user2 = User.objects.create_user(
            email="medico2@test.com",
            password=self.password,
            nombre="Ana",
            apellido="Rios",
            rol=User.Role.DOCTOR,
        )
        doctor2 = Doctor.objects.create(
            user=doctor_user2, identity_document="111111111", active=True
        )
        DoctorSpecialty.objects.create(doctor=doctor2, specialty=specialty2)
        for weekday in range(7):
            DoctorAvailability.objects.create(
                doctor=doctor2,
                specialty=specialty2,
                headquarters=self.headquarters,
                weekday=weekday,
                start_time=time(8, 0),
                end_time=time(17, 0),
                appointment_duration=30,
                active=True,
            )

        payload = self.booking_payload(
            doctor_id=doctor2.id,
            specialty_id=specialty2.id,
            scheduled_at=make_aware(self.test_date, time(10, 0)).isoformat(),
        )
        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("tope", str(response.data))

    def test_rejects_when_eps_has_no_remaining_budget(self):
        EPSBudget.objects.create(
            eps=self.eps,
            specialty=self.specialty,
            period_start=self.test_date.replace(day=1),
            period_end=self.test_date,
            total_budget=100,
            used_budget=100,
        )

        response = self.client.post(self.url, self.booking_payload(), format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("presupuestal", str(response.data))


    def test_requires_authentication(self):
        self.client.force_authenticate(user=None)

        response = self.client.post(self.url, self.booking_payload(), format="json")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    @patch("appointment.views.send_appointment_confirmation")
    def test_rescheduled_appointment_blocks_slot_for_other_booking(self, mock_email):
        # A RESCHEDULED appointment must be just as "occupying" a slot as a
        # CONFIRMED/PENDING one — it must not be invisible to slot validations.
        patient_user2 = User.objects.create_user(
            email="paciente2@test.com",
            password=self.password,
            nombre="Juan",
            apellido="Torres",
            rol=User.Role.PATIENT,
        )
        patient2 = Patient.objects.create(
            user=patient_user2,
            identity_document="999888777",
            document_type=Patient.DocumentType.CC,
            date_birth=date(1990, 1, 1),
            phone_number="+573001234568",
            address="Calle 1 # 2-3",
            eps=self.eps,
        )
        Appointment.objects.create(
            patient=patient2,
            doctor=self.doctor,
            specialty=self.specialty,
            headquarters=self.headquarters,
            scheduled_at=self.scheduled_at,
            duration_minutes=30,
            status=Appointment.Status.RESCHEDULED,
            created_by=patient_user2,
        )

        response = self.client.post(self.url, self.booking_payload(), format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Esta franja ya no está disponible", str(response.data))

    def test_rejects_booking_in_the_past(self):
        past_slot = timezone.now() - timedelta(days=1)
        response = self.client.post(
            self.url, self.booking_payload(scheduled_at=past_slot.isoformat()), format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("scheduled_at", response.data)

    def test_returns_400_when_required_fields_are_missing(self):
        response = self.client.post(self.url, {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("doctor_id", response.data)
        self.assertIn("specialty_id", response.data)
        self.assertIn("headquarters_id", response.data)

    @patch("appointment.views.send_appointment_confirmation")
    def test_does_not_apply_eps_validations_when_patient_eps_has_no_restrictions_configured(self, mock_email):
        EPSAppointmentLimit.objects.create(
            eps=self.eps,
            specialty=self.specialty,
            period=Period.MONTHLY,
            max_appointments=1,
            active=True,
        )
        Appointment.objects.create(
            patient=self.patient,
            doctor=self.doctor,
            specialty=self.specialty,
            headquarters=self.headquarters,
            scheduled_at=make_aware(self.test_date, time(8, 0)),
            duration_minutes=30,
            status=Appointment.Status.CONFIRMED,
            created_by=self.patient_user,
        )

        # En vez de asignar None (que viola el NOT NULL de la Base de Datos),
        # le creamos una EPS alternativa sin límites asociados para saltar la validación.
        particular_eps = EPS.objects.create(name="Particular / Sin EPS", code="PART01", active=True)
        self.patient.eps = particular_eps
        self.patient.save()

        response = self.client.post(self.url, self.booking_payload(), format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    @patch("appointment.views.send_appointment_confirmation")
    def test_does_not_apply_eps_validations_from_a_different_eps(self, mock_email):
        # A limit exhausted on a *different* EPS must not affect self.patient's booking,
        # since limits are scoped per-EPS.
        eps2 = EPS.objects.create(name="EPS Solo", code="EPS002", active=True)
        EPSAppointmentLimit.objects.create(
            eps=eps2,
            specialty=self.specialty,
            period=Period.MONTHLY,
            max_appointments=1,
            active=True,
        )
        # Pre-book to exhaust eps2's limit for another patient
        other_user = User.objects.create_user(
            email="otro_eps@test.com",
            password=self.password,
            nombre="Otro",
            apellido="EPS",
            rol=User.Role.PATIENT,
        )
        other_patient = Patient.objects.create(
            user=other_user,
            identity_document="000000002",
            document_type=Patient.DocumentType.CC,
            date_birth=date(1990, 1, 1),
            phone_number="+573001234572",
            address="Calle 1 # 2-3",
            eps=eps2,
        )
        Appointment.objects.create(
            patient=other_patient,
            doctor=self.doctor,
            specialty=self.specialty,
            headquarters=self.headquarters,
            scheduled_at=make_aware(self.test_date, time(8, 0)),
            duration_minutes=30,
            status=Appointment.Status.CONFIRMED,
            created_by=other_user,
        )

        # self.patient belongs to self.eps, which has no limit — booking must succeed
        response = self.client.post(self.url, self.booking_payload(), format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    @patch("appointment.views.send_appointment_confirmation")
    def test_increments_eps_used_budget_after_booking(self, mock_email):
        budget = EPSBudget.objects.create(
            eps=self.eps,
            specialty=self.specialty,
            period_start=self.test_date.replace(day=1),
            period_end=self.test_date,
            total_budget=10,
            used_budget=0,
        )

        self.client.post(self.url, self.booking_payload(), format="json")

        budget.refresh_from_db()
        self.assertEqual(budget.used_budget, 1)

    @patch("appointment.views.send_appointment_confirmation")
    def test_eps_budget_blocks_booking_after_limit_is_reached(self, mock_email):
        second_date = self.test_date + timedelta(days=1)
        EPSBudget.objects.create(
            eps=self.eps,
            specialty=self.specialty,
            period_start=self.test_date.replace(day=1),
            period_end=second_date,
            total_budget=1,
            used_budget=0,
        )
        first_slot = make_aware(self.test_date, time(9, 0))
        second_slot = make_aware(second_date, time(9, 0))

        self.client.post(self.url, self.booking_payload(scheduled_at=first_slot.isoformat()), format="json")
        response = self.client.post(self.url, self.booking_payload(scheduled_at=second_slot.isoformat()), format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("presupuestal", str(response.data))


class LimitAlertNotificationTests(AppointmentBookingSetupMixin, APITestCase):
    def setUp(self):
        self.url = reverse("appointment-create")
        self.build_scenario()
        self.superadmin = User.objects.create_user(
            email="superadmin@test.com",
            password=self.password,
            nombre="Super",
            apellido="Admin",
            rol=User.Role.SUPERADMIN,
        )
        self.limit = EPSAppointmentLimit.objects.create(
            eps=self.eps,
            specialty=self.specialty,
            period=Period.MONTHLY,
            max_appointments=10,
            active=True,
        )
        # Pre-fill 7 of the 10 slots directly (bypassing the API) so the next booking
        # reaches the 80% alert threshold (8/10).
        for hour in range(8, 15):
            Appointment.objects.create(
                patient=self.patient,
                doctor=self.doctor,
                specialty=self.specialty,
                headquarters=self.headquarters,
                scheduled_at=make_aware(self.test_date, time(hour, 0)),
                duration_minutes=30,
                status=Appointment.Status.CONFIRMED,
                created_by=self.patient_user,
            )

    @patch("appointment.views.send_appointment_confirmation")
    def test_creates_limit_alert_notification_for_superadmin_at_80_percent(self, mock_email):
        response = self.client.post(
            self.url,
            self.booking_payload(scheduled_at=make_aware(self.test_date, time(15, 0)).isoformat()),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        alerts = Notification.objects.filter(
            type=Notification.Type.LIMIT_ALERT, user=self.superadmin
        )
        self.assertEqual(alerts.count(), 1)

    @patch("appointment.views.send_appointment_confirmation")
    def test_does_not_duplicate_alert_within_same_period(self, mock_email):
        self.client.post(
            self.url,
            self.booking_payload(scheduled_at=make_aware(self.test_date, time(15, 0)).isoformat()),
            format="json",
        )
        response = self.client.post(
            self.url,
            self.booking_payload(scheduled_at=make_aware(self.test_date, time(15, 30)).isoformat()),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        alerts = Notification.objects.filter(
            type=Notification.Type.LIMIT_ALERT, user=self.superadmin
        )
        self.assertEqual(alerts.count(), 1)

    @patch("appointment.views.send_appointment_confirmation")
    def test_overlapping_active_limits_each_generate_their_own_alert(self, mock_email):
        # A second, general (specialty=None) weekly limit overlapping with the existing
        # specialty-specific monthly limit: both are active for the same EPS and both
        # should reach >= 80% usage with the same booking, so both must alert
        # independently (the general limit's alert must not be suppressed by the
        # specific one's, or vice versa).
        general_weekly_limit = EPSAppointmentLimit.objects.create(
            eps=self.eps,
            specialty=None,
            period=Period.WEEKLY,
            max_appointments=10,
            active=True,
        )

        response = self.client.post(
            self.url,
            self.booking_payload(scheduled_at=make_aware(self.test_date, time(15, 0)).isoformat()),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        alerts = Notification.objects.filter(type=Notification.Type.LIMIT_ALERT, user=self.superadmin)
        self.assertEqual(alerts.count(), 2)
        alerted_limit_ids = set(alerts.values_list("limit_id", flat=True))
        self.assertEqual(alerted_limit_ids, {self.limit.id, general_weekly_limit.id})

    @patch("appointment.views.send_appointment_confirmation")
    def test_next_period_generates_a_new_alert(self, mock_email):
        # Trigger the alert for the current month first.
        self.client.post(
            self.url,
            self.booking_payload(scheduled_at=make_aware(self.test_date, time(15, 0)).isoformat()),
            format="json",
        )
        self.assertEqual(
            Notification.objects.filter(
                type=Notification.Type.LIMIT_ALERT, user=self.superadmin, limit=self.limit
            ).count(),
            1,
        )

        next_month_date = self.test_date.replace(day=1)
        if next_month_date.month == 12:
            next_month_date = next_month_date.replace(year=next_month_date.year + 1, month=1, day=5)
        else:
            next_month_date = next_month_date.replace(month=next_month_date.month + 1, day=5)

        # Pre-fill 7 of the 10 slots for next month directly, then book the 8th via the
        # API so that period's usage also crosses the 80% threshold.
        for hour in range(8, 15):
            Appointment.objects.create(
                patient=self.patient,
                doctor=self.doctor,
                specialty=self.specialty,
                headquarters=self.headquarters,
                scheduled_at=make_aware(next_month_date, time(hour, 0)),
                duration_minutes=30,
                status=Appointment.Status.CONFIRMED,
                created_by=self.patient_user,
            )
        response = self.client.post(
            self.url,
            self.booking_payload(scheduled_at=make_aware(next_month_date, time(15, 0)).isoformat()),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            Notification.objects.filter(
                type=Notification.Type.LIMIT_ALERT, user=self.superadmin, limit=self.limit
            ).count(),
            2,
        )


class AppointmentListTests(AppointmentBookingSetupMixin, APITestCase):
    def setUp(self):
        self.url = reverse("appointment-list")
        self.build_scenario()

    def _create_appointment(self, slot_time=time(9, 0)):
        return Appointment.objects.create(
            patient=self.patient,
            doctor=self.doctor,
            specialty=self.specialty,
            headquarters=self.headquarters,
            scheduled_at=make_aware(self.test_date, slot_time),
            duration_minutes=30,
            status=Appointment.Status.CONFIRMED,
            created_by=self.patient_user,
        )

    def test_returns_appointments_for_authenticated_patient(self):
        self._create_appointment()

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_response_includes_expected_fields(self):
        self._create_appointment()

        response = self.client.get(self.url)

        appt = response.data[0]
        self.assertIn("id", appt)
        self.assertIn("doctor_name", appt)
        self.assertIn("specialty_name", appt)
        self.assertIn("scheduled_at", appt)
        self.assertIn("status", appt)

    def test_does_not_return_other_patients_appointments(self):
        self._create_appointment()
        patient_user2 = User.objects.create_user(
            email="otro@test.com",
            password=self.password,
            nombre="Otro",
            apellido="Paciente",
            rol=User.Role.PATIENT,
        )
        other_patient = Patient.objects.create(
            user=patient_user2,
            identity_document="000111222",
            document_type=Patient.DocumentType.CC,
            date_birth=date(1990, 1, 1),
            phone_number="+573001234569",
            address="Calle 1 # 2-3",
            eps=self.eps,
        )
        Appointment.objects.create(
            patient=other_patient,
            doctor=self.doctor,
            specialty=self.specialty,
            scheduled_at=make_aware(self.test_date, time(10, 0)),
            duration_minutes=30,
            status=Appointment.Status.CONFIRMED,
            created_by=patient_user2,
        )

        response = self.client.get(self.url)

        self.assertEqual(len(response.data), 1)
        self.assertIn("Maria", response.data[0].get("patient_name", "Maria"))

    def test_returns_empty_list_when_patient_has_no_appointments(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0)

    def test_requires_authentication(self):
        self.client.force_authenticate(user=None)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_rejects_non_patient_user(self):
        medico_user = User.objects.create_user(
            email="medico_test_list_block@test.com",
            password=self.password,
            nombre="Medico",
            apellido="Prueba",
            rol=User.Role.DOCTOR,  
        )
        self.client.force_authenticate(user=medico_user)

        # CAMBIO: Usar .get() en lugar de .post() y quitar el payload
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

class AppointmentDetailTests(AppointmentBookingSetupMixin, APITestCase):
    def setUp(self):
        self.build_scenario()

    def _create_appointment(self):
        return Appointment.objects.create(
            patient=self.patient,
            doctor=self.doctor,
            specialty=self.specialty,
            headquarters=self.headquarters,
            scheduled_at=make_aware(self.test_date, time(9, 0)),
            duration_minutes=30,
            status=Appointment.Status.CONFIRMED,
            created_by=self.patient_user,
        )

    def test_returns_full_appointment_detail(self):
        appointment = self._create_appointment()
        url = reverse("appointment-detail", args=[appointment.id])

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], appointment.id)
        self.assertIn("Carlos", response.data["doctor_name"])
        self.assertEqual(response.data["specialty_name"], "Medicina General")
        self.assertEqual(response.data["headquarters_name"], "Sede Central")
        self.assertEqual(response.data["status"], Appointment.Status.CONFIRMED)

    def test_rejects_access_to_another_patients_appointment(self):
        appointment = self._create_appointment()
        url = reverse("appointment-detail", args=[appointment.id])

        patient_user2 = User.objects.create_user(
            email="otro@test.com",
            password=self.password,
            nombre="Otro",
            apellido="Paciente",
            rol=User.Role.PATIENT,
        )
        Patient.objects.create(
            user=patient_user2,
            identity_document="000111222",
            document_type=Patient.DocumentType.CC,
            date_birth=date(1990, 1, 1),
            phone_number="+573001234570",
            address="Calle 1 # 2-3",
            eps=self.eps,
        )
        self.client.force_authenticate(user=patient_user2)

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_returns_400_for_nonexistent_appointment(self):
        url = reverse("appointment-detail", args=[99999])

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_requires_authentication(self):
        appointment = self._create_appointment()
        url = reverse("appointment-detail", args=[appointment.id])
        self.client.force_authenticate(user=None)

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class DoctorAppointmentListTests(AppointmentBookingSetupMixin, APITestCase):
    def setUp(self):
        self.url = reverse("doctor-appointment-list")
        self.build_scenario()

    def _create_appointment(self, slot_time=time(9, 0)):
        return Appointment.objects.create(
            patient=self.patient,
            doctor=self.doctor,
            specialty=self.specialty,
            headquarters=self.headquarters,
            scheduled_at=make_aware(self.test_date, slot_time),
            duration_minutes=30,
            status=Appointment.Status.CONFIRMED,
            created_by=self.patient_user,
        )

    def test_doctor_can_list_their_appointments(self):
        self._create_appointment()
        self.client.force_authenticate(user=self.doctor.user)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertIn("Maria", response.data[0]["patient_name"])

    def test_patient_cannot_access_doctor_appointment_list(self):
        self.client.force_authenticate(user=self.patient_user)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_requires_authentication(self):
        self.client.force_authenticate(user=None)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class AppointmentRescheduleTests(AppointmentBookingSetupMixin, APITestCase):
    def setUp(self):
        self.build_scenario()
        self.appointment = Appointment.objects.create(
            patient=self.patient,
            doctor=self.doctor,
            specialty=self.specialty,
            headquarters=self.headquarters,
            scheduled_at=self.scheduled_at,
            duration_minutes=30,
            status=Appointment.Status.CONFIRMED,
            created_by=self.patient_user,
        )
        self.url = reverse("appointment-reschedule", args=[self.appointment.id])
        self.new_scheduled_at = make_aware(self.test_date, time(11, 0))
        self.client.force_authenticate(user=self.doctor.user)

    def reschedule_payload(self, **overrides):
        payload = {
            "scheduled_at": self.new_scheduled_at.isoformat(),
            "reason": "El médico tuvo una emergencia",
        }
        payload.update(overrides)
        return payload

    @patch("appointment.views.send_appointment_rescheduled")
    def test_doctor_can_reschedule_appointment(self, mock_email):
        response = self.client.post(self.url, self.reschedule_payload(), format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.appointment.refresh_from_db()
        self.assertEqual(self.appointment.scheduled_at, self.new_scheduled_at)
        self.assertEqual(self.appointment.status, Appointment.Status.RESCHEDULED)
        self.assertEqual(response.data["status"], Appointment.Status.RESCHEDULED)

    @patch("appointment.views.send_appointment_rescheduled")
    def test_reschedule_creates_history_record(self, mock_email):
        self.client.post(self.url, self.reschedule_payload(), format="json")

        history = AppointmentHistory.objects.get(appointment=self.appointment)
        self.assertEqual(history.previous_scheduled_at, self.scheduled_at)
        self.assertEqual(history.new_scheduled_at, self.new_scheduled_at)
        self.assertEqual(history.changed_by, self.doctor.user)
        self.assertEqual(history.reason, "El médico tuvo una emergencia")

    @patch("appointment.views.send_appointment_rescheduled")
    def test_reschedule_sends_notification(self, mock_email):
        self.client.post(self.url, self.reschedule_payload(), format="json")

        mock_email.assert_called_once()
        appointment_arg = mock_email.call_args[0][0]
        previous_arg = mock_email.call_args[0][1]
        self.assertEqual(appointment_arg.pk, self.appointment.pk)
        self.assertEqual(previous_arg, self.scheduled_at)

    @patch("appointment.views.send_appointment_rescheduled")
    def test_rejects_when_new_slot_is_occupied_by_another_appointment_of_same_doctor(self, mock_email):
        patient_user2 = User.objects.create_user(
            email="paciente2@test.com",
            password=self.password,
            nombre="Juan",
            apellido="Torres",
            rol=User.Role.PATIENT,
        )
        patient2 = Patient.objects.create(
            user=patient_user2,
            identity_document="999888777",
            document_type=Patient.DocumentType.CC,
            date_birth=date(1990, 1, 1),
            phone_number="+573001234571",
            address="Calle 1 # 2-3",
            eps=self.eps,
        )
        Appointment.objects.create(
            patient=patient2,
            doctor=self.doctor,
            specialty=self.specialty,
            headquarters=self.headquarters,
            scheduled_at=self.new_scheduled_at,
            duration_minutes=30,
            status=Appointment.Status.CONFIRMED,
            created_by=patient_user2,
        )

        response = self.client.post(self.url, self.reschedule_payload(), format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Esta franja ya no está disponible", str(response.data))

    @patch("appointment.views.send_appointment_rescheduled")
    def test_rejects_when_patient_has_another_appointment_at_new_slot(self, mock_email):
        specialty2 = Specialty.objects.create(name="Dermatologia", active=True)
        doctor_user2 = User.objects.create_user(
            email="medico2@test.com",
            password=self.password,
            nombre="Ana",
            apellido="Rios",
            rol=User.Role.DOCTOR,
        )
        doctor2 = Doctor.objects.create(
            user=doctor_user2, identity_document="111111111", active=True
        )
        DoctorSpecialty.objects.create(doctor=doctor2, specialty=specialty2)
        for weekday in range(7):
            DoctorAvailability.objects.create(
                doctor=doctor2,
                specialty=specialty2,
                weekday=weekday,
                start_time=time(8, 0),
                end_time=time(17, 0),
                appointment_duration=30,
                active=True,
            )
        Appointment.objects.create(
            patient=self.patient,
            doctor=doctor2,
            specialty=specialty2,
            scheduled_at=self.new_scheduled_at,
            duration_minutes=30,
            status=Appointment.Status.CONFIRMED,
            created_by=self.patient_user,
        )

        response = self.client.post(self.url, self.reschedule_payload(), format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Ya tienes una cita agendada en ese horario", str(response.data))

    def test_rejects_when_new_slot_is_not_in_doctor_availability(self):
        response = self.client.post(
            self.url,
            self.reschedule_payload(scheduled_at=make_aware(self.test_date, time(23, 0)).isoformat()),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("no corresponde a una disponibilidad válida", str(response.data))

    def test_doctor_cannot_reschedule_another_doctors_appointment(self):
        doctor_user2 = User.objects.create_user(
            email="medico2@test.com",
            password=self.password,
            nombre="Ana",
            apellido="Rios",
            rol=User.Role.DOCTOR,
        )
        Doctor.objects.create(user=doctor_user2, identity_document="111111111", active=True)
        self.client.force_authenticate(user=doctor_user2)

        response = self.client.post(self.url, self.reschedule_payload(), format="json")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_rejects_reschedule_of_cancelled_appointment(self):
        self.appointment.status = Appointment.Status.CANCELLED
        self.appointment.save()

        response = self.client.post(self.url, self.reschedule_payload(), format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_rejects_reschedule_of_attended_appointment(self):
        self.appointment.status = Appointment.Status.ATTENDED
        self.appointment.save()

        response = self.client.post(self.url, self.reschedule_payload(), format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_patient_cannot_reschedule_appointment(self):
        self.client.force_authenticate(user=self.patient_user)

        response = self.client.post(self.url, self.reschedule_payload(), format="json")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_requires_authentication(self):
        self.client.force_authenticate(user=None)

        response = self.client.post(self.url, self.reschedule_payload(), format="json")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_rejects_reschedule_to_a_past_date(self):
        past_slot = timezone.now() - timedelta(days=1)
        response = self.client.post(
            self.url, self.reschedule_payload(scheduled_at=past_slot.isoformat()), format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("scheduled_at", response.data)

    @patch("appointment.views.send_appointment_rescheduled")
    def test_reschedule_rejected_when_new_period_eps_budget_is_exhausted(self, mock_email):
        # Budget for the original period (where self.appointment currently lives) has
        # plenty of room, but the budget covering the new date is already exhausted.
        next_month_date = (self.test_date.replace(day=1) + timedelta(days=32)).replace(day=5)
        EPSBudget.objects.create(
            eps=self.eps,
            specialty=self.specialty,
            period_start=self.test_date.replace(day=1),
            period_end=self.test_date,
            total_budget=100,
            used_budget=1,
        )
        next_period_budget = EPSBudget.objects.create(
            eps=self.eps,
            specialty=self.specialty,
            period_start=next_month_date.replace(day=1),
            period_end=next_month_date,
            total_budget=1,
            used_budget=1,
        )

        new_slot = make_aware(next_month_date, time(11, 0))
        response = self.client.post(
            self.url, self.reschedule_payload(scheduled_at=new_slot.isoformat()), format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("presupuestal", str(response.data))
        self.appointment.refresh_from_db()
        self.assertEqual(self.appointment.scheduled_at, self.scheduled_at)
        next_period_budget.refresh_from_db()
        self.assertEqual(next_period_budget.used_budget, 1)

    @patch("appointment.views.send_appointment_rescheduled")
    def test_reschedule_moves_eps_budget_usage_to_new_period(self, mock_email):
        next_month_date = (self.test_date.replace(day=1) + timedelta(days=32)).replace(day=5)
        original_budget = EPSBudget.objects.create(
            eps=self.eps,
            specialty=self.specialty,
            period_start=self.test_date.replace(day=1),
            period_end=self.test_date,
            total_budget=100,
            used_budget=1,
        )
        new_budget = EPSBudget.objects.create(
            eps=self.eps,
            specialty=self.specialty,
            period_start=next_month_date.replace(day=1),
            period_end=next_month_date,
            total_budget=100,
            used_budget=0,
        )

        new_slot = make_aware(next_month_date, time(11, 0))
        response = self.client.post(
            self.url, self.reschedule_payload(scheduled_at=new_slot.isoformat()), format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        original_budget.refresh_from_db()
        new_budget.refresh_from_db()
        self.assertEqual(original_budget.used_budget, 0)
        self.assertEqual(new_budget.used_budget, 1)


class AppointmentListFilterTests(AppointmentBookingSetupMixin, APITestCase):
    def setUp(self):
        self.url = reverse("appointment-list")
        self.build_scenario()

        self.other_specialty = Specialty.objects.create(name="Dermatologia", active=True)
        self.other_headquarters = Headquarters.objects.create(name="Sede Otra", active=True)
        doctor_user2 = User.objects.create_user(
            email="medico2@test.com",
            password=self.password,
            nombre="Ana",
            apellido="Rios",
            rol=User.Role.DOCTOR,
        )
        self.doctor2 = Doctor.objects.create(
            user=doctor_user2, identity_document="111111111", active=True
        )

        self.appointment1 = Appointment.objects.create(
            patient=self.patient,
            doctor=self.doctor,
            specialty=self.specialty,
            headquarters=self.headquarters,
            scheduled_at=make_aware(self.test_date, time(9, 0)),
            duration_minutes=30,
            status=Appointment.Status.CONFIRMED,
            created_by=self.patient_user,
        )
        self.appointment2 = Appointment.objects.create(
            patient=self.patient,
            doctor=self.doctor2,
            specialty=self.other_specialty,
            headquarters=self.other_headquarters,
            scheduled_at=make_aware(self.test_date, time(10, 0)),
            duration_minutes=30,
            status=Appointment.Status.CANCELLED,
            created_by=self.patient_user,
        )

    def test_filters_by_specialty(self):
        response = self.client.get(self.url, {"specialty": self.specialty.id})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["id"], self.appointment1.id)

    def test_filters_by_doctor(self):
        response = self.client.get(self.url, {"doctor": self.doctor2.id})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["id"], self.appointment2.id)

    def test_filters_by_status(self):
        response = self.client.get(self.url, {"status": Appointment.Status.CANCELLED})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["id"], self.appointment2.id)

    def test_filters_by_headquarters(self):
        response = self.client.get(self.url, {"headquarters": self.other_headquarters.id})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["id"], self.appointment2.id)

    def test_doctor_list_filters_by_specialty_and_status(self):
        doctor_url = reverse("doctor-appointment-list")
        self.client.force_authenticate(user=self.doctor.user)

        response = self.client.get(doctor_url, {"specialty": self.specialty.id, "status": Appointment.Status.CONFIRMED})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["id"], self.appointment1.id)


class AppointmentCancelTests(AppointmentBookingSetupMixin, APITestCase):
    def setUp(self):
        self.build_scenario()
        self.appointment = Appointment.objects.create(
            patient=self.patient,
            doctor=self.doctor,
            specialty=self.specialty,
            headquarters=self.headquarters,
            scheduled_at=self.scheduled_at,
            duration_minutes=30,
            status=Appointment.Status.CONFIRMED,
            created_by=self.patient_user,
        )
        self.url = reverse("appointment-cancel", args=[self.appointment.id])

    @patch("appointment.views.send_appointment_cancelled")
    def test_patient_can_cancel_own_appointment(self, mock_email):
        response = self.client.post(self.url, {"reason": "Ya no puedo asistir"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.appointment.refresh_from_db()
        self.assertEqual(self.appointment.status, Appointment.Status.CANCELLED)

    @patch("appointment.views.send_appointment_cancelled")
    def test_cancellation_refunds_eps_budget(self, mock_email):
        budget = EPSBudget.objects.create(
            eps=self.eps,
            specialty=self.specialty,
            period_start=self.test_date.replace(day=1),
            period_end=self.test_date,
            total_budget=10,
            used_budget=3,
        )

        response = self.client.post(self.url, {"reason": "Cambio de planes"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        budget.refresh_from_db()
        self.assertEqual(budget.used_budget, 2)

    @patch("appointment.views.send_appointment_cancelled")
    def test_cancellation_refund_never_goes_below_zero(self, mock_email):
        budget = EPSBudget.objects.create(
            eps=self.eps,
            specialty=self.specialty,
            period_start=self.test_date.replace(day=1),
            period_end=self.test_date,
            total_budget=10,
            used_budget=0,
        )

        response = self.client.post(self.url, {"reason": "Cambio de planes"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        budget.refresh_from_db()
        self.assertEqual(budget.used_budget, 0)


class AppointmentDoctorCancelTests(AppointmentBookingSetupMixin, APITestCase):
    def setUp(self):
        self.build_scenario()
        self.appointment = Appointment.objects.create(
            patient=self.patient,
            doctor=self.doctor,
            specialty=self.specialty,
            headquarters=self.headquarters,
            scheduled_at=self.scheduled_at,
            duration_minutes=30,
            status=Appointment.Status.CONFIRMED,
            created_by=self.patient_user,
        )
        self.url = reverse("appointment-doctor-cancel", args=[self.appointment.id])
        self.client.force_authenticate(user=self.doctor.user)

    @patch("appointment.views.send_appointment_cancelled")
    def test_doctor_can_cancel_own_appointment_with_reason(self, mock_email):
        response = self.client.post(self.url, {"reason": "El médico no podrá atender"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.appointment.refresh_from_db()
        self.assertEqual(self.appointment.status, Appointment.Status.CANCELLED)
        history = AppointmentHistory.objects.get(appointment=self.appointment)
        self.assertEqual(history.reason, "El médico no podrá atender")
        self.assertEqual(history.changed_by, self.doctor.user)

    def test_requires_reason(self):
        response = self.client.post(self.url, {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("reason", response.data)

    def test_rejects_blank_reason(self):
        response = self.client.post(self.url, {"reason": "   "}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("reason", response.data)

    def test_doctor_cannot_cancel_another_doctors_appointment(self):
        doctor_user2 = User.objects.create_user(
            email="medico2@test.com",
            password=self.password,
            nombre="Ana",
            apellido="Rios",
            rol=User.Role.DOCTOR,
        )
        Doctor.objects.create(user=doctor_user2, identity_document="111111111", active=True)
        self.client.force_authenticate(user=doctor_user2)

        response = self.client.post(self.url, {"reason": "No es mi cita"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_patient_cannot_use_doctor_cancel_endpoint(self):
        self.client.force_authenticate(user=self.patient_user)

        response = self.client.post(self.url, {"reason": "Intento no autorizado"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @patch("appointment.views.send_appointment_cancelled")
    def test_doctor_cancel_refunds_eps_budget(self, mock_email):
        budget = EPSBudget.objects.create(
            eps=self.eps,
            specialty=self.specialty,
            period_start=self.test_date.replace(day=1),
            period_end=self.test_date,
            total_budget=10,
            used_budget=5,
        )

        response = self.client.post(self.url, {"reason": "El médico tuvo una emergencia"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        budget.refresh_from_db()
        self.assertEqual(budget.used_budget, 4)

    @patch("appointment.views.send_appointment_cancelled")
    def test_rejects_cancelling_already_cancelled_appointment(self, mock_email):
        self.appointment.status = Appointment.Status.CANCELLED
        self.appointment.save()

        response = self.client.post(self.url, {"reason": "Otra vez"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
