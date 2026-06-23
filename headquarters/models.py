from django.db import models


class Headquarters(models.Model):
    name = models.CharField(max_length=150, unique=True,db_column="nombre")
    address = models.CharField(max_length=255, blank=True, db_column="direccion")
    phone = models.CharField(max_length=30, blank=True, db_column="telefono")
    active = models.BooleanField(default=True, db_column="activo")
    
    class Meta:
        db_table = "sedes"
        verbose_name = "sede"
        verbose_name_plural = "sedes"
        ordering = ["name"]

    def __str__(self):
        return self.name
    
    