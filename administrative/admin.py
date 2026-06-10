from django.contrib import admin

from .models import Administrative


@admin.register(Administrative)
class AdministrativeAdmin(admin.ModelAdmin):
    list_display = ("identity_document", "user", "headquarters", "position")
    list_filter = ("headquarters",)
    search_fields = (
        "identity_document",
        "user__nombre",
        "user__apellido",
        "user__email",
        "position",
    )
    autocomplete_fields = ("user", "headquarters")
