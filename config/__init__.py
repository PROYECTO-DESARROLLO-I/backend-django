# Esta línea asegura que Celery sea importado cuando Django inicia
from .celery import app as celery_app

__all__ = ("celery_app",)
