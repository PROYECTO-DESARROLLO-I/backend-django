from django.db import models


class DoctorAvailability(models.Model):
    class Weekday(models.IntegerChoices):
        MONDAY = 0, "Lunes"
        TUESDAY = 1, "Martes"
        WEDNESDAY = 2, "Miércoles"
        THURSDAY = 3, "Jueves"
        FRIDAY = 4, "Viernes"
        SATURDAY = 5, "Sábado"
        SUNDAY = 6, "Domingo"

    doctor = models.ForeignKey(
        "doctor.Doctor",
        on_delete=models.CASCADE,
        related_name="availabilities",
        db_column="medico_id",
    )
    specialty = models.ForeignKey(
        "specialties.Specialty",
        on_delete=models.CASCADE,
        related_name="doctor_availabilities",
        db_column="especialidad_id",
    )
    headquarters = models.ForeignKey(
        "headquarters.Headquarters",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="doctor_availabilities",
        db_column="sede_id",
    )
    weekday = models.PositiveSmallIntegerField(choices=Weekday.choices, db_column="dia_semana")
    start_time = models.TimeField(db_column="hora_inicio")
    end_time = models.TimeField(db_column="hora_fin")
    appointment_duration = models.PositiveIntegerField(db_column="duracion_cita")
    active = models.BooleanField(default=True, db_column="activo")

    class Meta:
        db_table = "disponibilidad_medico"
        verbose_name = "disponibilidad médica"
        verbose_name_plural = "disponibilidades médicas"
        ordering = ["doctor", "weekday", "start_time"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(weekday__gte=0, weekday__lte=6),
                name="doctor_availability_weekday_range",
            ),
            models.CheckConstraint(
                condition=models.Q(appointment_duration__gt=0),
                name="doctor_availability_positive_duration",
            ),
        ]

    def __str__(self):
        return f"{self.doctor} - {self.get_weekday_display()} {self.start_time}-{self.end_time}"


class ScheduleException(models.Model):
    class ExceptionType(models.TextChoices):
        BLOCK = "bloqueo", "Bloqueo"
        HOLIDAY = "feriado", "Feriado"
        VACATION = "vacaciones", "Vacaciones"

    doctor = models.ForeignKey(
        "doctor.Doctor",
        on_delete=models.CASCADE,
        related_name="schedule_exceptions",
        db_column="medico_id",
    )
    date = models.DateField(db_column="fecha")
    reason = models.CharField(max_length=255, blank=True, db_column="motivo")
    type = models.CharField(
        max_length=20,
        choices=ExceptionType.choices,
        blank=True,
        db_column="tipo",
    )

    class Meta:
        db_table = "excepciones_horario"
        verbose_name = "excepción de horario"
        verbose_name_plural = "excepciones de horario"
        ordering = ["doctor", "date"]

    def __str__(self):
        return f"{self.doctor} - {self.date} ({self.type or 'sin tipo'})"
