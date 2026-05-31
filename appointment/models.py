from django.db import models


class Appointment(models.Model):
    class Status(models.TextChoices):
        PENDING = "pendiente", "Pendiente"
        CONFIRMED = "confirmada", "Confirmada"
        CANCELLED = "cancelada", "Cancelada"
        RESCHEDULED = "reprogramada", "Reprogramada"
        ATTENDED = "atendida", "Atendida"

    patient = models.ForeignKey(
        "patient.Patient",
        on_delete=models.CASCADE,
        related_name="appointments",
        db_column="paciente_id",
    )
    doctor = models.ForeignKey(
        "doctor.Doctor",
        on_delete=models.CASCADE,
        related_name="appointments",
        db_column="medico_id",
    )
    specialty = models.ForeignKey(
        "specialties.Specialty",
        on_delete=models.CASCADE,
        related_name="appointments",
        db_column="especialidad_id",
    )
    headquarters = models.ForeignKey(
        "headquarters.Headquarters",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="appointments",
        db_column="sede_id",
    )
    scheduled_at = models.DateTimeField(db_column="fecha_hora")
    duration_minutes = models.PositiveIntegerField(db_column="duracion_minutos")
    status = models.CharField(max_length=20, choices=Status.choices, db_column="estado")
    created_by = models.ForeignKey(
        "user.User",
        on_delete=models.PROTECT,
        related_name="created_appointments",
        db_column="creado_por",
    )
    consultation_reason = models.CharField(max_length=255, blank=True, db_column="motivo_consulta")
    notes = models.TextField(blank=True, db_column="notas")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "citas"
        verbose_name = "cita"
        verbose_name_plural = "citas"
        ordering = ["scheduled_at"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(duration_minutes__gt=0),
                name="appointment_positive_duration",
            )
        ]

    def __str__(self):
        return f"Cita {self.patient} con {self.doctor} - {self.scheduled_at}"
