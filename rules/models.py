from django.db import models


class Period(models.TextChoices):
    WEEKLY = "semanal", "Semanal"
    MONTHLY = "mensual", "Mensual"


class EPSAppointmentLimit(models.Model):
    eps = models.ForeignKey(
        "eps.EPS",
        on_delete=models.CASCADE,
        related_name="appointment_limits",
        db_column="eps_id",
    )
    specialty = models.ForeignKey(
        "specialties.Specialty",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="eps_appointment_limits",
        db_column="especialidad_id",
    )
    period = models.CharField(max_length=20, choices=Period.choices, db_column="periodo")
    max_appointments = models.PositiveIntegerField(db_column="max_citas")
    active = models.BooleanField(default=True, db_column="activo")

    class Meta:
        db_table = "topes_citas_eps"
        verbose_name = "tope de citas EPS"
        verbose_name_plural = "topes de citas EPS"
        ordering = ["eps", "specialty", "period"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(max_appointments__gt=0),
                name="eps_appointment_limit_positive_max",
            ),
            models.UniqueConstraint(
                fields=["eps", "specialty", "period"],
                condition=models.Q(active=True),
                name="unique_active_eps_limit",
            ),
        ]

    def __str__(self):
        specialty = self.specialty or "Todas las especialidades"
        return f"{self.eps} - {specialty}: {self.max_appointments} ({self.period})"


class EPSBudget(models.Model):
    eps = models.ForeignKey(
        "eps.EPS",
        on_delete=models.CASCADE,
        related_name="budgets",
        db_column="eps_id",
    )
    specialty = models.ForeignKey(
        "specialties.Specialty",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="eps_budgets",
        db_column="especialidad_id",
    )
    period_start = models.DateField(db_column="periodo_inicio")
    period_end = models.DateField(db_column="periodo_fin")
    total_budget = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        db_column="presupuesto_total",
    )
    used_budget = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
        db_column="presupuesto_usado",
    )

    class Meta:
        db_table = "presupuesto_eps"
        verbose_name = "presupuesto EPS"
        verbose_name_plural = "presupuestos EPS"
        ordering = ["eps", "period_start"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(total_budget__gte=0),
                name="eps_budget_non_negative_total",
            ),
            models.CheckConstraint(
                condition=models.Q(used_budget__gte=0),
                name="eps_budget_non_negative_used",
            ),
            models.CheckConstraint(
                condition=models.Q(period_end__gte=models.F("period_start")),
                name="eps_budget_valid_period",
            ),
        ]

    def __str__(self):
        return f"{self.eps} {self.period_start} - {self.period_end}"


class FrequencyRestriction(models.Model):
    specialty = models.ForeignKey(
        "specialties.Specialty",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="frequency_restrictions",
        db_column="especialidad_id",
    )
    period = models.CharField(max_length=20, choices=Period.choices, db_column="periodo")
    max_appointments_per_patient = models.PositiveIntegerField(db_column="max_citas_paciente")

    class Meta:
        db_table = "restricciones_frecuencia"
        verbose_name = "restricción de frecuencia"
        verbose_name_plural = "restricciones de frecuencia"
        ordering = ["specialty", "period"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(max_appointments_per_patient__gt=0),
                name="frequency_restriction_positive_max",
            )
        ]

    def __str__(self):
        specialty = self.specialty or "Todas las especialidades"
        return f"{specialty}: {self.max_appointments_per_patient} ({self.period})"
