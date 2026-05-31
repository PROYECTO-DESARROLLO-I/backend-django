from django.contrib import admin

from .models import Doctor, DoctorSpecialty


class DoctorSpecialtyInline(admin.TabularInline):
    model = DoctorSpecialty
    extra = 1
    autocomplete_fields = ("specialty",)


@admin.register(Doctor)
class DoctorAdmin(admin.ModelAdmin):
    list_display = ("identity_document", "user", "register_number", "phone_number", "active")
    list_filter = ("active", "specialties")
    search_fields = ("identity_document", "register_number", "user__nombre", "user__apellido", "user__email")
    autocomplete_fields = ("user",)
    inlines = (DoctorSpecialtyInline,)


@admin.register(DoctorSpecialty)
class DoctorSpecialtyAdmin(admin.ModelAdmin):
    list_display = ("doctor", "specialty")
    search_fields = ("doctor__user__nombre", "doctor__user__apellido", "specialty__name")
    autocomplete_fields = ("doctor", "specialty")
