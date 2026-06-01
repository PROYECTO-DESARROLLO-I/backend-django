from rest_framework import generics, permissions

from .serializers import PatientRegistrationSerializer


class RegisterPatientView(generics.CreateAPIView):
    serializer_class = PatientRegistrationSerializer
    permission_classes = [permissions.AllowAny]
