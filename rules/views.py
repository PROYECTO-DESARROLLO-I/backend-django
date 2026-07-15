from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from rules.models import EPSAppointmentLimit, EPSBudget, FrequencyRestriction
from rules.serializers import (
    EPSAppointmentLimitSerializer,
    EPSBudgetSerializer,
    FrequencyRestrictionSerializer,
)
from rules.services import (
    DEFAULT_ALERT_THRESHOLD,
    get_eps_budget_alerts,
    get_eps_limit_alerts,
    resolve_alert_threshold,
)
from user.permissions import IsAdministrativeUser, IsSuperAdmin


class EPSAppointmentLimitListCreateView(generics.ListCreateAPIView):
    queryset = EPSAppointmentLimit.objects.select_related("eps", "specialty").all()
    serializer_class = EPSAppointmentLimitSerializer
    permission_classes = [IsAuthenticated, IsSuperAdmin]


class EPSAppointmentLimitDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = EPSAppointmentLimit.objects.select_related("eps", "specialty").all()
    serializer_class = EPSAppointmentLimitSerializer
    permission_classes = [IsAuthenticated, IsSuperAdmin]


class EPSBudgetListCreateView(generics.ListCreateAPIView):
    queryset = EPSBudget.objects.select_related("eps", "specialty").all()
    serializer_class = EPSBudgetSerializer
    permission_classes = [IsAuthenticated, IsSuperAdmin]


class EPSBudgetDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = EPSBudget.objects.select_related("eps", "specialty").all()
    serializer_class = EPSBudgetSerializer
    permission_classes = [IsAuthenticated, IsSuperAdmin]


class FrequencyRestrictionListCreateView(generics.ListCreateAPIView):
    queryset = FrequencyRestriction.objects.select_related("specialty").all()
    serializer_class = FrequencyRestrictionSerializer
    permission_classes = [IsAuthenticated, IsSuperAdmin]


class FrequencyRestrictionDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = FrequencyRestriction.objects.select_related("specialty").all()
    serializer_class = FrequencyRestrictionSerializer
    permission_classes = [IsAuthenticated, IsSuperAdmin]


class EPSRestrictionAlertsView(APIView):
    permission_classes = [IsAuthenticated, IsAdministrativeUser]

    def get(self, request):
        threshold = resolve_alert_threshold(request.query_params.get("threshold", DEFAULT_ALERT_THRESHOLD))

        alerts = get_eps_limit_alerts(threshold) + get_eps_budget_alerts(threshold)

        return Response({"threshold": threshold, "alerts": alerts})
