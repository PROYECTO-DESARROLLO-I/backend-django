from django.contrib import admin

from .models import Patient


@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = ("identity_document", "user", "document_type", "eps", "phone_number")
    list_filter = ("document_type", "eps")
    search_fields = ("identity_document", "user__nombre", "user__apellido", "user__email")
    autocomplete_fields = ("user", "eps")
