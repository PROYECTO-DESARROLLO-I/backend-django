from django.db import models


class EPS(models.Model):
    name = models.CharField(max_length=100, db_column="nombre")
    code = models.CharField(max_length=50, unique=True, db_column="codigo")
    active = models.BooleanField(default=True, db_column="activo")

    class Meta:
        db_table = "eps"
        verbose_name = "EPS"
        verbose_name_plural = "EPS"
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.code})"
