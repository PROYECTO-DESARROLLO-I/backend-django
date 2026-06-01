import os
from .base import *

DEBUG = True

INSTALLED_APPS += [
    "corsheaders",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    *MIDDLEWARE,
]

CORS_ALLOWED_ORIGINS = [
    "http://localhost:5173",
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("DB_NAME", "postgres"),
        "USER": os.getenv("DB_USER", "postgres"),
        "PASSWORD": os.getenv("DB_PASSWORD", ""),
        "HOST": os.getenv("DB_HOST", "localhost"),
        "PORT": os.getenv("DB_PORT", "5432"),
        "OPTIONS": {"sslmode": os.getenv("DB_SSLMODE", "prefer")},
    }
}
