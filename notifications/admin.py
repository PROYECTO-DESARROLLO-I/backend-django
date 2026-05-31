from django.contrib import admin

from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("appointment", "user", "type", "channel", "status", "sent_at", "created_at")
    list_filter = ("type", "channel", "status", "created_at")
    search_fields = ("user__email", "user__nombre", "user__apellido")
    autocomplete_fields = ("appointment", "user")
    readonly_fields = ("created_at",)
