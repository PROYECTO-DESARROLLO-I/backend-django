from django.contrib import admin

from .models import DoctorAvailability, ScheduleException


@admin.register(DoctorAvailability)
class DoctorAvailabilityAdmin(admin.ModelAdmin):
    list_display = ("doctor", "specialty", "headquarters", "weekday", "start_time", "end_time", "appointment_duration", "active")
    list_filter = ("weekday", "active", "specialty", "headquarters")
    search_fields = ("doctor__user__nombre", "doctor__user__apellido", "specialty__name")
    autocomplete_fields = ("doctor", "specialty", "headquarters")


@admin.register(ScheduleException)
class ScheduleExceptionAdmin(admin.ModelAdmin):
    list_display = ("doctor", "date", "type", "reason")
    list_filter = ("type", "date")
    search_fields = ("doctor__user__nombre", "doctor__user__apellido", "reason")
    autocomplete_fields = ("doctor",)
