"""
Signals (Disparadores) para el sistema de notificaciones de SaludAgendaX.

Los signals permiten que se disparen tareas de Celery automáticamente
cuando ocurren eventos como la creación, reprogramación o cancelación de citas,
sin tener que modificar los views.
"""

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone

from appointment.models import Appointment
from notifications.tasks import (
    send_appointment_confirmation_email,
    send_appointment_rescheduled_email,
    send_appointment_cancelled_email,
)


# Variable global para rastrear el estado anterior de la cita
_appointment_previous_state = {}


@receiver(pre_save, sender=Appointment)
def track_appointment_changes(sender, instance, **kwargs):
    """
    Signal que se ejecuta ANTES de guardar una cita.
    Guarda el estado anterior para detectar cambios en post_save.
    """
    try:
        old_instance = Appointment.objects.get(pk=instance.pk)
        _appointment_previous_state[instance.pk] = {
            "status": old_instance.status,
            "scheduled_at": old_instance.scheduled_at,
        }
    except Appointment.DoesNotExist:
        # Es una cita nueva, no hay estado anterior
        _appointment_previous_state[instance.pk] = None


@receiver(post_save, sender=Appointment)
def handle_appointment_changes(sender, instance, created, **kwargs):
    """
    Signal que se ejecuta DESPUÉS de guardar una cita.
    Dispara las tareas de notificación correspondientes según el evento.
    
    Eventos detectados:
    - Creación: Nueva cita confirmada
    - Reprogramación: El horario cambió
    - Cancelación: El estado cambió a CANCELLED
    """
    
    previous_state = _appointment_previous_state.pop(instance.pk, None)
    
    # ── EVENTO: CREACIÓN DE CITA ─────────────────────────────────────────
    if created:
        # Disparar tarea asíncrona de confirmación
        send_appointment_confirmation_email.delay(instance.pk)
        return
    
    # ── EVENTO: REPROGRAMACIÓN DE CITA ───────────────────────────────────
    if previous_state and previous_state["scheduled_at"] != instance.scheduled_at:
        # El horario fue modificado
        send_appointment_rescheduled_email.delay(
            instance.pk,
            previous_state["scheduled_at"].isoformat()
        )
        return
    
    # ── EVENTO: CANCELACIÓN DE CITA ──────────────────────────────────────
    if previous_state and previous_state["status"] != Appointment.Status.CANCELLED \
            and instance.status == Appointment.Status.CANCELLED:
        # El estado cambió a CANCELLED (detectar quién lo canceló desde el request)
        # Por ahora, disparar con el usuario que realizó la acción
        # Nota: El usuario se pasa desde la vista en el request.user
        send_appointment_cancelled_email.delay(instance.pk, instance.created_by_id)
        return
