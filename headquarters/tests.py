from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from headquarters.models import Headquarters

User = get_user_model()


class HeadquartersAPITest(APITestCase):
    def setUp(self):
        # 1. Superadministrador (Tiene acceso total)
        self.superadmin = User.objects.create_superuser(
            email="superadmin@example.com",
            password="Super1234!",
            nombre="Super",
            apellido="Admin",
        )

        # 2. Administrativo Regular (Tiene acceso a crear y listar sedes)
        self.admin_user = User.objects.create_user(
            email="admin@example.com",
            password="Admin1234!",
            nombre="Admin",
            apellido="User",
            rol=User.Role.ADMINISTRATIVE,
        )

        # 3. Paciente de prueba (Este rol SÍ debe ser bloqueado con 403)
        self.patient_user = User.objects.create_user(
            email="paciente@example.com",
            password="Patient1234!",
            nombre="Juan",
            apellido="Paciente",
            rol=User.Role.PATIENT,  # Ajusta según el nombre exacto de tu rol Paciente
        )

        self.payload_sede = {
            "name": "Sede Norte Cali",
            "address": "Calle 33 #34-15",
            "phone": "3154876520",
        }

        self.url = "/api/headquarters/"

    def test_superadmin_can_create_headquarters(self):
        """Valida que el superadmin pueda crear una sede con éxito"""
        self.client.force_authenticate(user=self.superadmin)
        response = self.client.post(self.url, self.payload_sede, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Headquarters.objects.count(), 1)

    def test_administrative_user_can_create_headquarters(self):
        """Valida que un usuario con rol administrativo regular SÍ pueda crear una sede"""
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.post(self.url, self.payload_sede, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)  # Esperamos 201 exitoso
        self.assertEqual(Headquarters.objects.count(), 1)

    def test_duplicate_name_returns_bad_request(self):
        """Valida la restricción de unicidad del nombre exigida en el backend"""
        Headquarters.objects.create(
            name=self.payload_sede["name"],
            address="Calle Antigua",
            phone="000000",
        )

        self.client.force_authenticate(user=self.superadmin)
        response = self.client.post(self.url, self.payload_sede, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unauthorized_roles_cannot_access_headquarters_endpoints(self):
        """Valida que usuarios sin roles administrativos (como pacientes) reciban 403 Forbidden"""
        self.client.force_authenticate(user=self.patient_user)  # Autenticamos al Paciente

        # Intentar registrar (Debe bloquearse)
        create_response = self.client.post(self.url, self.payload_sede, format="json")
        self.assertEqual(create_response.status_code, status.HTTP_403_FORBIDDEN)

        # Intentar listar (Debe bloquearse)
        list_response = self.client.get(self.url)
        self.assertEqual(list_response.status_code, status.HTTP_403_FORBIDDEN)

    def test_superadmin_can_list_headquarters(self):
        """Valida el listado correcto de sedes creadas"""
        Headquarters.objects.create(
            name="Sede Central",
            address="Carrera 5 #10-10",
            phone="3100000000",
        )

        self.client.force_authenticate(user=self.superadmin)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)