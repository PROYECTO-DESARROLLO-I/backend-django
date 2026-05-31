from django.db import models


class Administrative(models.Model):
    user = models.OneToOneField(
        "user.User",
        on_delete=models.CASCADE,
        related_name="administrative_profile",
        db_column="usuario_id",
    )
    headquarters = models.ForeignKey(
        "headquarters.Headquarters",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="administratives",
        db_column="sede_id",
    )
    position = models.CharField(max_length=100, blank=True, db_column="cargo")

    class Meta:
        db_table = "administrativos"
        verbose_name = "administrativo"
        verbose_name_plural = "administrativos"
        ordering = ["user__apellido", "user__nombre"]

    def __str__(self):
        return f"{self.user.nombre} {self.user.apellido} - {self.position or 'Administrativo'}"
