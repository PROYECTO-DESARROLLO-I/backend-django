from django.db import models


class Notification(models.Model):
    class Type(models.TextChoices):
        CONFIRMATION = "confirmacion", "Confirmación"
        REMINDER = "recordatorio", "Recordatorio"
        CANCELLATION = "cancelacion", "Cancelación"
        LIMIT_ALERT = "alerta_tope", "Alerta de tope"
        RESCHEDULED = "reprogramacion", "Reprogramación"

    class Status(models.TextChoices):
        PENDING = "pendiente", "Pendiente"
        SENT = "enviada", "Enviada"
        FAILED = "fallida", "Fallida"

    appointment = models.ForeignKey(
        "appointment.Appointment",
        on_delete=models.CASCADE,
        related_name="notifications",
        db_column="cita_id",
    )
    user = models.ForeignKey(
        "user.User",
        on_delete=models.CASCADE,
        related_name="notifications",
        db_column="usuario_id",
    )
    # Nullable: only set for LIMIT_ALERT notifications, to identify exactly which
    # EPSAppointmentLimit triggered the alert (needed for correct deduplication when
    # several active limits for the same EPS overlap in time). Additive field, does
    # not change the existing DBML relations.
    limit = models.ForeignKey(
        "rules.EPSAppointmentLimit",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notifications",
        db_column="tope_id",
    )
    type = models.CharField(max_length=20, choices=Type.choices, db_column="tipo")
    channel = models.CharField(max_length=30, default="email", db_column="canal")
    status = models.CharField(max_length=20, choices=Status.choices, db_column="estado")
    sent_at = models.DateTimeField(null=True, blank=True, db_column="enviada_at")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "notificaciones"
        verbose_name = "notificación"
        verbose_name_plural = "notificaciones"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.type} para {self.user} ({self.status})"
