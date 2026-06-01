from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils import timezone


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("El correo electrónico es obligatorio")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        extra_fields.setdefault("rol", User.Role.SUPERADMIN)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("El superusuario debe tener is_staff=True")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("El superusuario debe tener is_superuser=True")

        return self._create_user(email, password, **extra_fields)


class User(AbstractUser):
    class Role(models.TextChoices):
        PATIENT = "paciente", "Paciente"
        ADMINISTRATIVE = "administrativo", "Administrativo"
        DOCTOR = "medico", "Médico"
        SUPERADMIN = "superadmin", "Superadmin"

    username = None
    password = models.CharField(max_length=128, db_column="password_hash")
    first_name = None
    last_name = None
    nombre = models.CharField(max_length=150)
    apellido = models.CharField(max_length=150)
    email = models.EmailField(unique=True)
    rol = models.CharField(max_length=20, choices=Role.choices)
    is_active = models.BooleanField(default=True, db_column="activo")
    failed_login_attempts = models.PositiveSmallIntegerField(
        default=0,
        db_column="intentos_fallidos_login",
    )
    locked_until = models.DateTimeField(
        null=True,
        blank=True,
        db_column="bloqueado_hasta",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["nombre", "apellido"]
    objects = UserManager()

    class Meta:
        db_table = "usuarios"
        verbose_name = "usuario"
        verbose_name_plural = "usuarios"

    def __str__(self):
        return f"{self.nombre} {self.apellido} <{self.email}>"

    def is_temporarily_locked(self, now=None):
        now = now or timezone.now()
        return self.locked_until is not None and self.locked_until > now

    def login_lock_expired(self, now=None):
        now = now or timezone.now()
        return self.locked_until is not None and self.locked_until <= now

    def register_failed_login(self, now=None):
        now = now or timezone.now()
        max_attempts = getattr(settings, "AUTH_MAX_FAILED_LOGIN_ATTEMPTS", 5)
        lockout_minutes = getattr(settings, "AUTH_LOGIN_LOCKOUT_MINUTES", 15)

        self.failed_login_attempts += 1
        if self.failed_login_attempts >= max_attempts:
            self.locked_until = now + timedelta(minutes=lockout_minutes)

        self.save(
            update_fields=[
                "failed_login_attempts",
                "locked_until",
                "updated_at",
            ]
        )

    def reset_failed_login_attempts(self):
        self.failed_login_attempts = 0
        self.locked_until = None
        self.save(
            update_fields=[
                "failed_login_attempts",
                "locked_until",
                "updated_at",
            ]
        )
