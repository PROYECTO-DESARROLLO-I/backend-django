from django.urls import path
from .views import (
    DashboardKPIView,
    AppointmentSearchView,
    SpecialtyStatsView,
    ReportExportView,
    AlertsView,
)

urlpatterns = [
    path('kpis/',                DashboardKPIView.as_view(),     name='dashboard-kpis'),
    path('appointments/',        AppointmentSearchView.as_view(), name='dashboard-appointments'),
    path('specialties/stats/',   SpecialtyStatsView.as_view(),   name='dashboard-specialty-stats'),
    path('reports/export/',      ReportExportView.as_view(),     name='dashboard-export'),
    path('alerts/',              AlertsView.as_view(),           name='dashboard-alerts'),
]