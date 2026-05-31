from django.contrib import admin

from .models import Administrative


@admin.register(Administrative)
class AdministrativeAdmin(admin.ModelAdmin):
    list_display = ("user", "headquarters", "position")
    list_filter = ("headquarters",)
    search_fields = ("user__nombre", "user__apellido", "user__email", "position")
    autocomplete_fields = ("user", "headquarters")
