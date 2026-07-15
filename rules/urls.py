from django.urls import path

from rules.views import (
    EPSAppointmentLimitDetailView,
    EPSAppointmentLimitListCreateView,
    EPSBudgetDetailView,
    EPSBudgetListCreateView,
    EPSRestrictionAlertsView,
    FrequencyRestrictionDetailView,
    FrequencyRestrictionListCreateView,
)

urlpatterns = [
    path("limits/", EPSAppointmentLimitListCreateView.as_view(), name="rules-limit-list"),
    path("limits/<int:pk>/", EPSAppointmentLimitDetailView.as_view(), name="rules-limit-detail"),
    path("budgets/", EPSBudgetListCreateView.as_view(), name="rules-budget-list"),
    path("budgets/<int:pk>/", EPSBudgetDetailView.as_view(), name="rules-budget-detail"),
    path("frequency/", FrequencyRestrictionListCreateView.as_view(), name="rules-frequency-list"),
    path("frequency/<int:pk>/", FrequencyRestrictionDetailView.as_view(), name="rules-frequency-detail"),
    path("alerts/", EPSRestrictionAlertsView.as_view(), name="rules-alerts"),
]
