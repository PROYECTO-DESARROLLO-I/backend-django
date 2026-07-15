from datetime import date, time, timedelta

from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from appointment.models import Appointment
from doctor.models import Doctor
from eps.models import EPS
from headquarters.models import Headquarters
from patient.models import Patient
from rules.models import EPSAppointmentLimit, EPSBudget, FrequencyRestriction, Period
from specialties.models import Specialty
from user.models import User


def make_aware(d, t):
    return timezone.make_aware(timezone.datetime.combine(d, t))


class RulesTestSetupMixin:
    password = "ClaveSegura123*"

    def build_scenario(self):
        self.eps = EPS.objects.create(name="EPS Test", code="EPS001", active=True)
        self.specialty = Specialty.objects.create(name="Medicina General", active=True)
        self.headquarters = Headquarters.objects.create(name="Sede Central", active=True)

        self.superadmin = User.objects.create_user(
            email="superadmin@test.com",
            password=self.password,
            nombre="Super",
            apellido="Admin",
            rol=User.Role.SUPERADMIN,
        )
        self.administrative = User.objects.create_user(
            email="administrativo@test.com",
            password=self.password,
            nombre="Admin",
            apellido="Personal",
            rol=User.Role.ADMINISTRATIVE,
        )
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
            eps=self.eps,
            date_birth="2000-01-01",
        )
        self.patient_user = patient_user

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

    def create_appointments(self, count, specialty=None, scheduled_date=None):
        specialty = specialty or self.specialty
        scheduled_date = scheduled_date or date.today()
        for i in range(count):
            Appointment.objects.create(
                patient=self.patient,
                doctor=self.doctor,
                specialty=specialty,
                headquarters=self.headquarters,
                scheduled_at=make_aware(scheduled_date, time(8, 0)),
                duration_minutes=30,
                status=Appointment.Status.CONFIRMED,
                created_by=self.patient_user,
            )


class EPSAppointmentLimitCRUDTests(RulesTestSetupMixin, APITestCase):
    def setUp(self):
        self.build_scenario()
        self.list_url = reverse("rules-limit-list")

    def _payload(self):
        return {
            "eps": self.eps.id,
            "specialty": self.specialty.id,
            "period": Period.MONTHLY,
            "max_appointments": 10,
            "active": True,
        }

    def test_superadmin_can_create_limit(self):
        self.client.force_authenticate(user=self.superadmin)

        response = self.client.post(self.list_url, self._payload(), format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_superadmin_can_list_update_and_delete_limit(self):
        self.client.force_authenticate(user=self.superadmin)
        limit = EPSAppointmentLimit.objects.create(
            eps=self.eps, specialty=self.specialty, period=Period.MONTHLY, max_appointments=5, active=True
        )
        detail_url = reverse("rules-limit-detail", args=[limit.id])

        list_response = self.client.get(self.list_url)
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)

        update_response = self.client.patch(detail_url, {"max_appointments": 20}, format="json")
        self.assertEqual(update_response.status_code, status.HTTP_200_OK)
        self.assertEqual(update_response.data["max_appointments"], 20)

        delete_response = self.client.delete(detail_url)
        self.assertEqual(delete_response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(EPSAppointmentLimit.objects.filter(id=limit.id).exists())

    def test_administrative_user_forbidden(self):
        self.client.force_authenticate(user=self.administrative)

        response = self.client.post(self.list_url, self._payload(), format="json")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_patient_forbidden(self):
        self.client.force_authenticate(user=self.patient_user)

        response = self.client.post(self.list_url, self._payload(), format="json")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_requires_authentication(self):
        response = self.client.post(self.list_url, self._payload(), format="json")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_rejects_duplicate_active_limit(self):
        self.client.force_authenticate(user=self.superadmin)
        EPSAppointmentLimit.objects.create(
            eps=self.eps, specialty=self.specialty, period=Period.MONTHLY, max_appointments=5, active=True
        )

        response = self.client.post(self.list_url, self._payload(), format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Ya existe un tope activo", str(response.data))


class EPSRestrictionAlertsTests(RulesTestSetupMixin, APITestCase):
    def setUp(self):
        self.build_scenario()
        self.url = reverse("rules-alerts")

    def test_warning_alert_at_80_percent_usage(self):
        EPSAppointmentLimit.objects.create(
            eps=self.eps, specialty=self.specialty, period=Period.MONTHLY, max_appointments=10, active=True
        )
        self.create_appointments(8)
        self.client.force_authenticate(user=self.superadmin)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        limit_alerts = [a for a in response.data["alerts"] if a["type"] == "tope_citas"]
        self.assertEqual(len(limit_alerts), 1)
        self.assertEqual(limit_alerts[0]["usage_percent"], 80.0)
        self.assertEqual(limit_alerts[0]["level"], "warning")

    def test_critical_alert_at_100_percent_usage(self):
        EPSAppointmentLimit.objects.create(
            eps=self.eps, specialty=self.specialty, period=Period.MONTHLY, max_appointments=10, active=True
        )
        self.create_appointments(10)
        self.client.force_authenticate(user=self.superadmin)

        response = self.client.get(self.url)

        limit_alerts = [a for a in response.data["alerts"] if a["type"] == "tope_citas"]
        self.assertEqual(len(limit_alerts), 1)
        self.assertEqual(limit_alerts[0]["level"], "critical")

    def test_no_alert_below_threshold(self):
        EPSAppointmentLimit.objects.create(
            eps=self.eps, specialty=self.specialty, period=Period.MONTHLY, max_appointments=10, active=True
        )
        self.create_appointments(3)
        self.client.force_authenticate(user=self.superadmin)

        response = self.client.get(self.url)

        limit_alerts = [a for a in response.data["alerts"] if a["type"] == "tope_citas"]
        self.assertEqual(len(limit_alerts), 0)

    def test_budget_alert_at_80_percent_usage(self):
        today = date.today()
        EPSBudget.objects.create(
            eps=self.eps,
            specialty=self.specialty,
            period_start=today.replace(day=1),
            period_end=today + timedelta(days=5),
            total_budget=100,
            used_budget=80,
        )
        self.client.force_authenticate(user=self.superadmin)

        response = self.client.get(self.url)

        budget_alerts = [a for a in response.data["alerts"] if a["type"] == "presupuesto"]
        self.assertEqual(len(budget_alerts), 1)
        self.assertEqual(budget_alerts[0]["level"], "warning")

    def test_administrative_can_view_alerts(self):
        self.client.force_authenticate(user=self.administrative)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_patient_forbidden(self):
        self.client.force_authenticate(user=self.patient_user)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_global_limit_without_specialty_counts_all_specialties(self):
        other_specialty = Specialty.objects.create(name="Odontologia", active=True)
        EPSAppointmentLimit.objects.create(
            eps=self.eps, specialty=None, period=Period.MONTHLY, max_appointments=10, active=True
        )
        self.create_appointments(4, specialty=self.specialty)
        self.create_appointments(4, specialty=other_specialty)
        self.client.force_authenticate(user=self.superadmin)

        response = self.client.get(self.url)

        limit_alerts = [a for a in response.data["alerts"] if a["type"] == "tope_citas"]
        self.assertEqual(len(limit_alerts), 1)
        self.assertEqual(limit_alerts[0]["used"], 8)
        self.assertIsNone(limit_alerts[0]["specialty"])
        self.assertEqual(limit_alerts[0]["usage_percent"], 80.0)

    def test_invalid_threshold_falls_back_to_default(self):
        EPSAppointmentLimit.objects.create(
            eps=self.eps, specialty=self.specialty, period=Period.MONTHLY, max_appointments=10, active=True
        )
        self.create_appointments(8)
        self.client.force_authenticate(user=self.superadmin)

        for invalid_value in ["abc", "-1", "nan", "2", "inf"]:
            response = self.client.get(self.url, {"threshold": invalid_value})

            self.assertEqual(response.status_code, status.HTTP_200_OK, invalid_value)
            self.assertEqual(response.data["threshold"], 0.8, invalid_value)
            limit_alerts = [a for a in response.data["alerts"] if a["type"] == "tope_citas"]
            self.assertEqual(len(limit_alerts), 1, invalid_value)
