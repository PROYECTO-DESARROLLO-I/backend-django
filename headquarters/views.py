from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import Headquarters
from .serializers import HeadquartersSerializer
from user.permissions import IsAdministrativeUser

class HeadquartersListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated, IsAdministrativeUser]

    def get(self, request):
        sedes = Headquarters.objects.filter(active=True)
        serializer = HeadquartersSerializer(sedes, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        serializer = HeadquartersSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(
                {
                    "message": "La sede fue registrada correctamente.",
                    "data": serializer.data
                },
                status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)