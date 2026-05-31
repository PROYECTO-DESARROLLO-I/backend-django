from django.contrib import admin

from .models import EPSAppointmentLimit, EPSBudget, FrequencyRestriction


@admin.register(EPSAppointmentLimit)
class EPSAppointmentLimitAdmin(admin.ModelAdmin):
    list_display = ("eps", "specialty", "period", "max_appointments", "active")
    list_filter = ("period", "active", "eps", "specialty")
    autocomplete_fields = ("eps", "specialty")


@admin.register(EPSBudget)
class EPSBudgetAdmin(admin.ModelAdmin):
    list_display = ("eps", "specialty", "period_start", "period_end", "total_budget", "used_budget")
    list_filter = ("eps", "specialty", "period_start", "period_end")
    autocomplete_fields = ("eps", "specialty")


@admin.register(FrequencyRestriction)
class FrequencyRestrictionAdmin(admin.ModelAdmin):
    list_display = ("specialty", "period", "max_appointments_per_patient")
    list_filter = ("period", "specialty")
    autocomplete_fields = ("specialty",)
