from django.contrib import admin

from .models import Headquarters


@admin.register(Headquarters)
class HeadquartersAdmin(admin.ModelAdmin):
    list_display = ("name", "phone", "active")
    list_filter = ("active",)
    search_fields = ("name", "address", "phone")
