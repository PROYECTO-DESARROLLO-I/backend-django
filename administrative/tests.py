from datetime import date

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from eps.models import EPS
from patient.models import Patient
from user.models import User

from .models import Administrative


class AdministrativeStatusViewTests(APITestCase):
    """Pruebas para los endpoints POST /api/administratives/<id>/deactivate/ y /activate/"""

    password = "ClaveSegura123*"

    def setUp(self):
        self.administrative_user = User.objects.create_user(
            email="administrativo@test.com",
            password=self.password,
            nombre="Ana",
            apellido="Ramirez",
            rol=User.Role.ADMINISTRATIVE,
        )
        self.administrative = Administrative.objects.create(
            user=self.administrative_user,
            identity_document="10203040",
            position="Recepcion",
        )

        self.superadmin_user = User.objects.create_user(
            email="superadmin@test.com",
            password=self.password,
            nombre="Super",
            apellido="Admin",
            rol=User.Role.SUPERADMIN,
        )

        self.deactivate_url = reverse(
            "administrative-deactivate", args=[self.administrative.pk]
        )
        self.activate_url = reverse(
            "administrative-activate", args=[self.administrative.pk]
        )

    def test_superadmin_can_deactivate_administrative(self):
        self.client.force_authenticate(user=self.superadmin_user)

        response = self.client.post(self.deactivate_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.administrative_user.refresh_from_db()
        self.assertFalse(self.administrative_user.is_active)

    def test_superadmin_can_reactivate_administrative(self):
        self.administrative_user.is_active = False
        self.administrative_user.save(update_fields=["is_active"])
        self.client.force_authenticate(user=self.superadmin_user)

        response = self.client.post(self.activate_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.administrative_user.refresh_from_db()
        self.assertTrue(self.administrative_user.is_active)

    def test_administrative_receives_403(self):
        self.client.force_authenticate(user=self.administrative_user)

        response = self.client.post(self.deactivate_url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_patient_receives_403(self):
        eps = EPS.objects.create(name="SURA", code="SURA001", active=True)
        patient_user = User.objects.create_user(
            email="paciente@test.com",
            password=self.password,
            nombre="Juan",
            apellido="Garcia",
            rol=User.Role.PATIENT,
        )
        Patient.objects.create(
            user=patient_user,
            identity_document="12345678",
            document_type=Patient.DocumentType.CC,
            date_birth=date(1990, 5, 15),
            phone_number="3015551234",
            address="Calle 1 #2-3",
            eps=eps,
        )
        self.client.force_authenticate(user=patient_user)

        response = self.client.post(self.deactivate_url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_unauthenticated_user_receives_401(self):
        response = self.client.post(self.deactivate_url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_nonexistent_administrative_receives_404(self):
        self.client.force_authenticate(user=self.superadmin_user)

        url = reverse("administrative-deactivate", args=[999999])
        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_deactivate_twice_receives_400(self):
        self.client.force_authenticate(user=self.superadmin_user)

        first_response = self.client.post(self.deactivate_url)
        second_response = self.client.post(self.deactivate_url)

        self.assertEqual(first_response.status_code, status.HTTP_200_OK)
        self.assertEqual(second_response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_superadmin_cannot_deactivate_self(self):
        superadmin_administrative = Administrative.objects.create(
            user=self.superadmin_user,
            identity_document="90909090",
            position="Direccion",
        )
        self.client.force_authenticate(user=self.superadmin_user)

        url = reverse("administrative-deactivate", args=[superadmin_administrative.pk])
        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.superadmin_user.refresh_from_db()
        self.assertTrue(self.superadmin_user.is_active)

    def test_superadmin_cannot_deactivate_another_superadmin(self):
        other_superadmin_user = User.objects.create_user(
            email="otro_superadmin@test.com",
            password=self.password,
            nombre="Otro",
            apellido="Super",
            rol=User.Role.SUPERADMIN,
        )
        other_superadmin_administrative = Administrative.objects.create(
            user=other_superadmin_user,
            identity_document="80808080",
            position="Direccion",
        )
        self.client.force_authenticate(user=self.superadmin_user)

        url = reverse(
            "administrative-deactivate", args=[other_superadmin_administrative.pk]
        )
        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        other_superadmin_user.refresh_from_db()
        self.assertTrue(other_superadmin_user.is_active)

    def test_reactivate_normal_administrative_still_works(self):
        self.administrative_user.is_active = False
        self.administrative_user.save(update_fields=["is_active"])
        self.client.force_authenticate(user=self.superadmin_user)

        response = self.client.post(self.activate_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.administrative_user.refresh_from_db()
        self.assertTrue(self.administrative_user.is_active)
        self.assertTrue(response.data["data"]["is_active"])
