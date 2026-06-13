from django.db import models


class Patient(models.Model):
    class DocumentType(models.TextChoices):
        CC = "CC", "Cédula de ciudadanía"
        TI = "TI", "Tarjeta de identidad"
        CE = "CE", "Cédula de extranjería"
        PAS = "PAS", "Pasaporte"

    user = models.OneToOneField(
        "user.User",
        on_delete=models.CASCADE,
        related_name="patient_profile",
        db_column="usuario_id",
    )
    identity_document = models.CharField(
        max_length=50,
        unique=True,
        db_column="documento_identidad",
    )
    document_type = models.CharField(
        max_length=3,
        choices=DocumentType.choices,
        blank=True,
        db_column="tipo_documento",
    )
    date_birth = models.DateField(null=True, blank=True, db_column="fecha_nacimiento")
    phone_number = models.CharField(max_length=30, blank=True, db_column="telefono")
    address = models.CharField(max_length=255, blank=True, db_column="direccion")
    eps = models.ForeignKey(
        "eps.EPS",
        on_delete=models.PROTECT,
        null=True,
        related_name="patients",
        db_column="eps_id",
    )

    class Meta:
        db_table = "pacientes"
        verbose_name = "paciente"
        verbose_name_plural = "pacientes"
        ordering = ["user__apellido", "user__nombre"]

    def __str__(self):
        return f"{self.user.nombre} {self.user.apellido} - {self.identity_document}"
