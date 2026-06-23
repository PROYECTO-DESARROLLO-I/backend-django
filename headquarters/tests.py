from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from headquarters.models import Headquarters

User = get_user_model()


class HeadquartersAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()

        # Creamos el usuario base con create_user para asegurar que guarde el rol
        self.superadmin = User.objects.create_superuser(
            email="superadmin@example.com",
            password="Super1234!",
            nombre="Super",
            apellido="Admin",
        )

        # Crear el administrativo regular para pruebas de restricción
        self.admin_user = User.objects.create_user(
            email="admin@example.com",
            password="Admin1234!",
            nombre="Admin",
            apellido="User",
            rol=User.Role.ADMINISTRATIVE,
        )

        self.payload_sede = {
            "name": "Sede Norte Cali",
            "address": "Calle 33 #34-15",
            "phone": "3154876520",
        }

        self.url = "/api/headquarters/"

    def test_superadmin_can_create_headquarters(self):
        """Valida que el superadmin pueda crear una sede con los datos de React"""
        self.client.force_authenticate(user=self.superadmin)
        response = self.client.post(self.url, self.payload_sede, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Headquarters.objects.count(), 1)

        headquarters = Headquarters.objects.get()
        self.assertEqual(headquarters.name, self.payload_sede["name"])

    def test_duplicate_name_returns_bad_request(self):
        """Valida la restricción de unicidad del nombre exigida en el backend"""
        # Creamos una sede previa con el mismo nombre
        Headquarters.objects.create(
            name=self.payload_sede["name"],
            address="Calle Antigua",
            phone="000000",
        )

        self.client.force_authenticate(user=self.superadmin)
        response = self.client.post(self.url, self.payload_sede, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_non_superadmin_cannot_access_headquarters_endpoints(self):
        """Valida que usuarios sin rol SUPERADMIN reciban 403 Forbidden"""
        self.client.force_authenticate(user=self.admin_user)

        # Intentar registrar
        create_response = self.client.post(self.url, self.payload_sede, format="json")
        self.assertEqual(create_response.status_code, status.HTTP_403_FORBIDDEN)

        # Intentar listar
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
        self.assertEqual(response.data[0]["name"], "Sede Central")