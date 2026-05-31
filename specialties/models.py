from django.db import models


class Specialty(models.Model):
    name = models.CharField(max_length=150, unique=True, db_column="nombre")
    description = models.TextField(blank=True, db_column="descripcion")
    active = models.BooleanField(default=True, db_column="activo")

    class Meta:
        db_table = "especialidades"
        verbose_name = "especialidad"
        verbose_name_plural = "especialidades"
        ordering = ["name"]

    def __str__(self):
        return self.name
