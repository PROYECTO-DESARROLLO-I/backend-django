import os
from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F401,F403

DEBUG = os.getenv("DEBUG", "False") == "True"

ALLOWED_HOSTS = [
    host.strip() for host in os.getenv("ALLOWED_HOSTS", "").split(",") if host.strip()
]
if not ALLOWED_HOSTS:
    raise ImproperlyConfigured(
        "ALLOWED_HOSTS no está definida. Configura la IP pública o el dominio del "
        "EC2 en la variable de entorno ALLOWED_HOSTS (.env.production)."
    )

CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CSRF_TRUSTED_ORIGINS", "").split(",")
    if origin.strip()
]

if not SECRET_KEY or SECRET_KEY == "django-insecure-local-development-key":  # noqa: F405
    raise ImproperlyConfigured(
        "SECRET_KEY no está definida (o usa el valor inseguro por defecto). "
        "Genera una clave nueva y defínela en SECRET_KEY (.env.production): "
        "los JWT se firman con ella y con el valor por defecto serían falsificables."
    )

# Necesario cuando el backend está detrás de un proxy/ALB/CloudFront que
# termina TLS y reenvía las peticiones por HTTP.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Hardening de cookies. Si todavía se está probando por http:// sin HTTPS
# delante (CloudFront/ALB), pon estas dos en False temporalmente: solo
# afecta al admin de Django, ya que el API usa JWT por header.
SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "True") == "True"
CSRF_COOKIE_SECURE = os.getenv("CSRF_COOKIE_SECURE", "True") == "True"
SECURE_SSL_REDIRECT = os.getenv("SECURE_SSL_REDIRECT", "False") == "True"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("DB_NAME", "postgres"),
        "USER": os.getenv("DB_USER", "postgres"),
        "PASSWORD": os.getenv("DB_PASSWORD", ""),
        "HOST": os.getenv("DB_HOST"),
        "PORT": os.getenv("DB_PORT", "5432"),
        "OPTIONS": {"sslmode": os.getenv("DB_SSLMODE", "require")},
    }
}
