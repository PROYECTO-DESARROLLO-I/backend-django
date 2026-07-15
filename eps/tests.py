from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from eps.models import EPS
from user.models import User


class EPSTestSetupMixin:
    password = "ClaveSegura123*"

    def build_scenario(self):
        self.active_eps = EPS.objects.create(name="Sura", code="SURA01", active=True)
        self.inactive_eps = EPS.objects.create(name="Compensar", code="COMP01", active=False)

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
        self.patient_user = User.objects.create_user(
            email="paciente@test.com",
            password=self.password,
            nombre="Maria",
            apellido="Lopez",
            rol=User.Role.PATIENT,
        )


class EPSListTests(EPSTestSetupMixin, APITestCase):
    def setUp(self):
        self.build_scenario()
        self.url = reverse("eps-list")

    def test_public_listing_only_returns_active_eps(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        codes = [item["code"] for item in response.data]
        self.assertIn(self.active_eps.code, codes)
        self.assertNotIn(self.inactive_eps.code, codes)

    def test_non_superadmin_authenticated_user_only_sees_active_eps(self):
        self.client.force_authenticate(user=self.patient_user)

        response = self.client.get(self.url)

        codes = [item["code"] for item in response.data]
        self.assertIn(self.active_eps.code, codes)
        self.assertNotIn(self.inactive_eps.code, codes)

    def test_superadmin_sees_inactive_eps_too(self):
        self.client.force_authenticate(user=self.superadmin)

        response = self.client.get(self.url)

        codes = [item["code"] for item in response.data]
        self.assertIn(self.active_eps.code, codes)
        self.assertIn(self.inactive_eps.code, codes)

    def test_free_text_name_is_allowed(self):
        self.client.force_authenticate(user=self.superadmin)

        response = self.client.post(
            self.url, {"name": "Sanitas", "code": "SANI01", "active": True}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["name"], "Sanitas")

    def test_superadmin_can_create_eps(self):
        self.client.force_authenticate(user=self.superadmin)

        response = self.client.post(
            self.url, {"name": "Nueva EPS", "code": "NEW01", "active": True}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_administrative_cannot_create_eps(self):
        self.client.force_authenticate(user=self.administrative)

        response = self.client.post(
            self.url, {"name": "Nueva EPS", "code": "NEW01", "active": True}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_patient_cannot_create_eps(self):
        self.client.force_authenticate(user=self.patient_user)

        response = self.client.post(
            self.url, {"name": "Nueva EPS", "code": "NEW01", "active": True}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_unauthenticated_cannot_create_eps(self):
        response = self.client.post(
            self.url, {"name": "Nueva EPS", "code": "NEW01", "active": True}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_rejects_duplicate_code(self):
        self.client.force_authenticate(user=self.superadmin)

        response = self.client.post(
            self.url, {"name": "Duplicada", "code": self.active_eps.code, "active": True}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Ya existe una EPS registrada con este código", str(response.data))


class EPSDetailTests(EPSTestSetupMixin, APITestCase):
    def setUp(self):
        self.build_scenario()
        self.url = reverse("eps-detail", args=[self.active_eps.id])

    def test_superadmin_can_update_eps(self):
        self.client.force_authenticate(user=self.superadmin)

        response = self.client.patch(self.url, {"name": "Sura EPS"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "Sura EPS")

    def test_superadmin_can_delete_eps(self):
        self.client.force_authenticate(user=self.superadmin)

        response = self.client.delete(self.url)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(EPS.objects.filter(id=self.active_eps.id).exists())

    def test_administrative_forbidden_on_update(self):
        self.client.force_authenticate(user=self.administrative)

        response = self.client.patch(self.url, {"name": "Sura EPS"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_patient_forbidden_on_retrieve(self):
        self.client.force_authenticate(user=self.patient_user)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_patient_forbidden_on_delete(self):
        self.client.force_authenticate(user=self.patient_user)

        response = self.client.delete(self.url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_unauthenticated_forbidden_on_update(self):
        response = self.client.patch(self.url, {"name": "Sura EPS"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
