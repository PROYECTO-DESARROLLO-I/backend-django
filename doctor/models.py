from django.db import models


class Doctor(models.Model):
    user = models.OneToOneField(
        "user.User",
        on_delete=models.CASCADE,
        related_name="doctor_profile",
        db_column="usuario_id",
    )
    identity_document = models.CharField(
        max_length=50,
        unique=True,
        db_column="documento_identidad",
    )
    register_number = models.CharField(
        max_length=100,
        unique=True,
        null=True,
        blank=True,
        db_column="numero_registro",
    )
    academic_information = models.TextField(blank=True, db_column="informacion_academica")
    phone_number = models.CharField(max_length=30, blank=True, db_column="telefono")
    active = models.BooleanField(default=True, db_column="activo")
    specialties = models.ManyToManyField(
        "specialties.Specialty",
        through="DoctorSpecialty",
        related_name="doctors",
    )

    class Meta:
        db_table = "medicos"
        verbose_name = "médico"
        verbose_name_plural = "médicos"
        ordering = ["user__apellido", "user__nombre"]

    def __str__(self):
        return f"Dr(a). {self.user.nombre} {self.user.apellido}"


class DoctorSpecialty(models.Model):
    doctor = models.ForeignKey(
        "doctor.Doctor",
        on_delete=models.CASCADE,
        related_name="doctor_specialties",
        db_column="medico_id",
    )
    specialty = models.ForeignKey(
        "specialties.Specialty",
        on_delete=models.CASCADE,
        related_name="doctor_specialties",
        db_column="especialidad_id",
    )

    class Meta:
        db_table = "medico_especialidades"
        verbose_name = "especialidad de médico"
        verbose_name_plural = "especialidades de médicos"
        constraints = [
            models.UniqueConstraint(
                fields=["doctor", "specialty"],
                name="unique_doctor_specialty",
            )
        ]

    def __str__(self):
        return f"{self.doctor} - {self.specialty}"
