"""
Celery configuration for SaludAgendaX project.

Este módulo configura Celery como broker de tareas asíncronas usando Redis.
Se conecta automáticamente a Django durante la inicialización.
"""

import os
from celery import Celery
from celery.utils.log import get_task_logger

# Establecer el módulo de configuración por defecto
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

# Crear la instancia de Celery
app = Celery("saludagendax")

# Cargar la configuración desde Django settings usando namespace "CELERY"
app.config_from_object("django.conf:settings", namespace="CELERY")

# Autodiscover de tareas en todas las apps de Django
app.autodiscover_tasks()

# Logger para Celery tasks
logger = get_task_logger(__name__)


@app.task(bind=True)
def debug_task(self):
    """Tarea de prueba para verificar que Celery está funcionando correctamente."""
    logger.info(f"Request: {self.request!r}")
