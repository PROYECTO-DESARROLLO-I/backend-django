from django.db import models


class EPS(models.Model):
    class Name(models.TextChoices):
        SURA = "SURA", "Sura"
        COMPENSAR = "COMPENSAR", "Compensar"
        FAMISANAR = "FAMISANAR", "Famisanar"
        MEDISALUD = "MEDISALUD", "Medisalud"

    name = models.CharField(max_length=50, choices=Name.choices, db_column="nombre")
    code = models.CharField(max_length=50, unique=True, db_column="codigo")
    active = models.BooleanField(default=True, db_column="activo")

    class Meta:
        db_table = "eps"
        verbose_name = "EPS"
        verbose_name_plural = "EPS"
        ordering = ["name"]

    def __str__(self):
        # show human-readable choice label when available
        try:
            display = self.get_name_display()
        except Exception:
            display = self.name
        return f"{display} ({self.code})"
