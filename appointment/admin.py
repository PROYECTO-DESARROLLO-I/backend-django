from django.contrib import admin

from .models import Appointment


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ("scheduled_at", "patient", "doctor", "specialty", "headquarters", "status")
    list_filter = ("status", "specialty", "headquarters", "scheduled_at")
    search_fields = ("patient__identity_document", "doctor__user__nombre", "doctor__user__apellido", "consultation_reason")
    autocomplete_fields = ("patient", "doctor", "specialty", "headquarters", "created_by")
    readonly_fields = ("created_at", "updated_at")
