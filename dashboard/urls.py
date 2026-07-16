from django.urls import path
from .views import (
    DashboardKPIView,
    AppointmentSearchView,
    SpecialtyStatsView,
    ReportExportView,
    AlertsView,
)

from specialties.views import SpecialtyAdminListCreateView, SpecialtyAdminDetailView

urlpatterns = [
    path('kpis/',                 DashboardKPIView.as_view(),     name='dashboard-kpis'),
    path('appointments/',         AppointmentSearchView.as_view(), name='dashboard-appointments'),
    path('specialties/stats/',    SpecialtyStatsView.as_view(),   name='dashboard-specialty-stats'),
    path('specialties/',          SpecialtyAdminListCreateView.as_view(), name='dashboard-specialties'),
    path('specialties/<int:pk>/', SpecialtyAdminDetailView.as_view(),     name='dashboard-specialty-detail'),
    path('reports/export/',       ReportExportView.as_view(),     name='dashboard-export'),
    path('alerts/',               AlertsView.as_view(),           name='dashboard-alerts'),
]