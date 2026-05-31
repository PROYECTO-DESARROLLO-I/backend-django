from django.contrib import admin

from .models import EPS


@admin.register(EPS)
class EPSAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "active")
    list_filter = ("active",)
    search_fields = ("name", "code")
