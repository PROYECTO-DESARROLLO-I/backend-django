from django.apps import AppConfig


class NotificationsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "notifications"

    def ready(self):
        """
        Se ejecuta cuando Django inicia. Registra los signals de la app.
        """
        import notifications.signals  # noqa: F401
