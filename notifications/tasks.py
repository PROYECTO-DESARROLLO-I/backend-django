"""
Tareas asíncronas de Celery para el sistema de notificaciones de SaludAgendaX.

Estas tareas se ejecutan en segundo plano usando Redis como broker,
permitiendo que la API no se bloquee durante el envío de correos.
"""

from celery import shared_task
from celery.utils.log import get_task_logger
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone
from datetime import timedelta

from appointment.models import Appointment
from notifications.models import Notification

logger = get_task_logger(__name__)


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 3, "countdown": 60},  # Reintentar 3 veces cada 60 segundos
    default_retry_delay=60,
)
def send_appointment_confirmation_email(self, appointment_id):
    """
    Envía correo de confirmación de cita al paciente y al médico.
    Se ejecuta de forma asíncrona cuando se crea una cita.
    
    Args:
        appointment_id: ID de la cita a notificar
    """
    try:
        appointment = Appointment.objects.select_related(
            "patient__user", "doctor__user", "specialty", "headquarters"
        ).get(pk=appointment_id)
        
        patient_user = appointment.patient.user
        doctor_user = appointment.doctor.user
        scheduled_local = timezone.localtime(appointment.scheduled_at)
        
        # Preparar contexto para plantilla
        context = {
            "patient_name": patient_user.nombre,
            "doctor_name": f"Dr(a). {doctor_user.nombre} {doctor_user.apellido}",
            "specialty": appointment.specialty.name,
            "scheduled_at": scheduled_local.strftime("%d/%m/%Y %H:%M"),
            "duration_minutes": appointment.duration_minutes,
            "headquarters": appointment.headquarters.name if appointment.headquarters else "No especificada",
            "appointment_id": appointment.pk,
            "contact_email": settings.DEFAULT_FROM_EMAIL,
        }
        
        # Crear notificación para paciente
        patient_notification = Notification.objects.create(
            appointment=appointment,
            user=patient_user,
            type=Notification.Type.CONFIRMATION,
            channel="email",
            status=Notification.Status.PENDING,
        )
        
        # Renderizar plantilla HTML
        html_content = render_to_string("notifications/appointment_confirmation.html", context)
        
        # Crear y enviar correo a paciente
        email = EmailMultiAlternatives(
            subject=f"Confirmación de cita médica — {appointment.specialty.name}",
            body="Por favor, abre este correo en un cliente que soporte HTML.",
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[patient_user.email],
        )
        email.attach_alternative(html_content, "text/html")
        email.send(fail_silently=False)
        
        patient_notification.status = Notification.Status.SENT
        patient_notification.sent_at = timezone.now()
        patient_notification.save(update_fields=["status", "sent_at"])
        
        logger.info(f"✓ Confirmación enviada al paciente: {patient_user.email}")
        
        # Crear notificación para médico
        doctor_notification = Notification.objects.create(
            appointment=appointment,
            user=doctor_user,
            type=Notification.Type.CONFIRMATION,
            channel="email",
            status=Notification.Status.PENDING,
        )
        
        context["patient_name"] = f"{patient_user.nombre} {patient_user.apellido}"
        html_content = render_to_string("notifications/appointment_confirmation_doctor.html", context)
        
        email = EmailMultiAlternatives(
            subject=f"Nueva cita confirmada — {appointment.specialty.name}",
            body="Por favor, abre este correo en un cliente que soporte HTML.",
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[doctor_user.email],
        )
        email.attach_alternative(html_content, "text/html")
        email.send(fail_silently=False)
        
        doctor_notification.status = Notification.Status.SENT
        doctor_notification.sent_at = timezone.now()
        doctor_notification.save(update_fields=["status", "sent_at"])
        
        logger.info(f"✓ Confirmación enviada al médico: {doctor_user.email}")
        
    except Appointment.DoesNotExist:
        logger.error(f"Appointment not found: {appointment_id}")
        raise
    except Exception as e:
        logger.error(f"Error sending appointment confirmation: {str(e)}")
        # Actualizar notificaciones a fallidas si existen
        try:
            Notification.objects.filter(
                appointment_id=appointment_id,
                type=Notification.Type.CONFIRMATION,
                status=Notification.Status.PENDING
            ).update(
                status=Notification.Status.FAILED,
                error_message=str(e)[:500]
            )
        except Exception:
            pass
        raise


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 3, "countdown": 60},
)
def send_appointment_rescheduled_email(self, appointment_id, previous_scheduled_at):
    """
    Envía correo de reprogramación de cita al paciente y al médico.
    
    Args:
        appointment_id: ID de la cita reprogramada
        previous_scheduled_at: Datetime anterior (string en formato ISO)
    """
    try:
        from datetime import datetime
        
        appointment = Appointment.objects.select_related(
            "patient__user", "doctor__user", "specialty", "headquarters"
        ).get(pk=appointment_id)
        
        patient_user = appointment.patient.user
        doctor_user = appointment.doctor.user
        previous_local = timezone.localtime(datetime.fromisoformat(previous_scheduled_at))
        new_local = timezone.localtime(appointment.scheduled_at)
        
        # Contexto para plantilla
        context = {
            "patient_name": patient_user.nombre,
            "doctor_name": f"Dr(a). {doctor_user.nombre} {doctor_user.apellido}",
            "specialty": appointment.specialty.name,
            "previous_scheduled_at": previous_local.strftime("%d/%m/%Y %H:%M"),
            "new_scheduled_at": new_local.strftime("%d/%m/%Y %H:%M"),
            "headquarters": appointment.headquarters.name if appointment.headquarters else "No especificada",
            "appointment_id": appointment.pk,
        }
        
        # Notificación a paciente
        patient_notification = Notification.objects.create(
            appointment=appointment,
            user=patient_user,
            type=Notification.Type.RESCHEDULED,
            channel="email",
            status=Notification.Status.PENDING,
        )
        
        html_content = render_to_string("notifications/appointment_rescheduled.html", context)
        email = EmailMultiAlternatives(
            subject=f"Reprogramación de cita médica — {appointment.specialty.name}",
            body="Por favor, abre este correo en un cliente que soporte HTML.",
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[patient_user.email],
        )
        email.attach_alternative(html_content, "text/html")
        email.send(fail_silently=False)
        
        patient_notification.status = Notification.Status.SENT
        patient_notification.sent_at = timezone.now()
        patient_notification.save(update_fields=["status", "sent_at"])
        
        logger.info(f"✓ Reprogramación enviada al paciente: {patient_user.email}")
        
        # Notificación a médico
        doctor_notification = Notification.objects.create(
            appointment=appointment,
            user=doctor_user,
            type=Notification.Type.RESCHEDULED,
            channel="email",
            status=Notification.Status.PENDING,
        )
        
        context["patient_name"] = f"{patient_user.nombre} {patient_user.apellido}"
        html_content = render_to_string("notifications/appointment_rescheduled_doctor.html", context)
        email = EmailMultiAlternatives(
            subject=f"Cita reprogramada — {previous_local.strftime('%d/%m/%Y %H:%M')}",
            body="Por favor, abre este correo en un cliente que soporte HTML.",
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[doctor_user.email],
        )
        email.attach_alternative(html_content, "text/html")
        email.send(fail_silently=False)
        
        doctor_notification.status = Notification.Status.SENT
        doctor_notification.sent_at = timezone.now()
        doctor_notification.save(update_fields=["status", "sent_at"])
        
        logger.info(f"✓ Reprogramación enviada al médico: {doctor_user.email}")
        
    except Exception as e:
        logger.error(f"Error sending rescheduled email: {str(e)}")
        try:
            Notification.objects.filter(
                appointment_id=appointment_id,
                type=Notification.Type.RESCHEDULED,
                status=Notification.Status.PENDING
            ).update(
                status=Notification.Status.FAILED,
                error_message=str(e)[:500]
            )
        except Exception:
            pass
        raise


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 3, "countdown": 60},
)
def send_appointment_cancelled_email(self, appointment_id, cancelled_by_id):
    """
    Envía correo de cancelación de cita al paciente y al médico.
    
    Args:
        appointment_id: ID de la cita cancelada
        cancelled_by_id: ID del usuario que canceló (paciente, médico o administrativo)
    """
    try:
        from user.models import User
        
        appointment = Appointment.objects.select_related(
            "patient__user", "doctor__user", "specialty", "headquarters"
        ).get(pk=appointment_id)
        
        cancelled_by = User.objects.get(pk=cancelled_by_id)
        patient_user = appointment.patient.user
        doctor_user = appointment.doctor.user
        scheduled_local = timezone.localtime(appointment.scheduled_at)
        
        # Determinar quién canceló
        canceller_role = dict(User.Role.choices).get(cancelled_by.rol, "Sistema")
        
        context = {
            "patient_name": patient_user.nombre,
            "doctor_name": f"Dr(a). {doctor_user.nombre} {doctor_user.apellido}",
            "specialty": appointment.specialty.name,
            "scheduled_at": scheduled_local.strftime("%d/%m/%Y %H:%M"),
            "headquarters": appointment.headquarters.name if appointment.headquarters else "No especificada",
            "cancelled_by_role": canceller_role,
            "appointment_id": appointment.pk,
            "frontend_url": settings.FRONTEND_URL,
        }
        
        # Notificación a paciente
        patient_notification = Notification.objects.create(
            appointment=appointment,
            user=patient_user,
            type=Notification.Type.CANCELLATION,
            channel="email",
            status=Notification.Status.PENDING,
        )
        
        html_content = render_to_string("notifications/appointment_cancelled.html", context)
        email = EmailMultiAlternatives(
            subject=f"Cancelación de cita médica — {appointment.specialty.name}",
            body="Por favor, abre este correo en un cliente que soporte HTML.",
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[patient_user.email],
        )
        email.attach_alternative(html_content, "text/html")
        email.send(fail_silently=False)
        
        patient_notification.status = Notification.Status.SENT
        patient_notification.sent_at = timezone.now()
        patient_notification.save(update_fields=["status", "sent_at"])
        
        logger.info(f"✓ Cancelación enviada al paciente: {patient_user.email}")
        
        # Notificación a médico
        doctor_notification = Notification.objects.create(
            appointment=appointment,
            user=doctor_user,
            type=Notification.Type.CANCELLATION,
            channel="email",
            status=Notification.Status.PENDING,
        )
        
        context["patient_name"] = f"{patient_user.nombre} {patient_user.apellido}"
        html_content = render_to_string("notifications/appointment_cancelled_doctor.html", context)
        email = EmailMultiAlternatives(
            subject=f"Cita cancelada — {scheduled_local.strftime('%d/%m/%Y %H:%M')}",
            body="Por favor, abre este correo en un cliente que soporte HTML.",
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[doctor_user.email],
        )
        email.attach_alternative(html_content, "text/html")
        email.send(fail_silently=False)
        
        doctor_notification.status = Notification.Status.SENT
        doctor_notification.sent_at = timezone.now()
        doctor_notification.save(update_fields=["status", "sent_at"])
        
        logger.info(f"✓ Cancelación enviada al médico: {doctor_user.email}")
        
    except Exception as e:
        logger.error(f"Error sending cancelled email: {str(e)}")
        try:
            Notification.objects.filter(
                appointment_id=appointment_id,
                type=Notification.Type.CANCELLATION,
                status=Notification.Status.PENDING
            ).update(
                status=Notification.Status.FAILED,
                error_message=str(e)[:500]
            )
        except Exception:
            pass
        raise


@shared_task
def send_appointment_reminders():
    """
    Tarea periódica que envía recordatorios 24 horas antes de las citas confirmadas.
    Se ejecuta cada hora (ver CELERY_BEAT_SCHEDULE en settings).
    """
    logger.info("▶ Iniciando búsqueda de citas para recordatorios...")
    
    try:
        now = timezone.now()
        # Buscar citas confirmadas que ocurran en las próximas 24 horas
        tomorrow = now + timedelta(hours=24)
        
        appointments = Appointment.objects.filter(
            status=Appointment.Status.CONFIRMED,
            scheduled_at__gte=now,
            scheduled_at__lte=tomorrow,
        ).select_related("patient__user", "doctor__user", "specialty", "headquarters")
        
        reminder_count = 0
        for appointment in appointments:
            # Verificar si ya existe un recordatorio enviado para esta cita
            existing_reminder = Notification.objects.filter(
                appointment=appointment,
                type=Notification.Type.REMINDER,
                status=Notification.Status.SENT,
            ).exists()
            
            if existing_reminder:
                logger.debug(f"Recordatorio ya enviado para cita #{appointment.pk}")
                continue
            
            patient_user = appointment.patient.user
            scheduled_local = timezone.localtime(appointment.scheduled_at)
            
            context = {
                "patient_name": patient_user.nombre,
                "doctor_name": f"Dr(a). {appointment.doctor.user.nombre} {appointment.doctor.user.apellido}",
                "specialty": appointment.specialty.name,
                "scheduled_at": scheduled_local.strftime("%d/%m/%Y %H:%M"),
                "duration_minutes": appointment.duration_minutes,
                "headquarters": appointment.headquarters.name if appointment.headquarters else "No especificada",
                "appointment_id": appointment.pk,
            }
            
            # Crear notificación de recordatorio
            reminder_notification = Notification.objects.create(
                appointment=appointment,
                user=patient_user,
                type=Notification.Type.REMINDER,
                channel="email",
                status=Notification.Status.PENDING,
            )
            
            try:
                html_content = render_to_string("notifications/appointment_reminder.html", context)
                email = EmailMultiAlternatives(
                    subject=f"Recordatorio: Tu cita con {context['doctor_name']} en 24 horas",
                    body="Por favor, abre este correo en un cliente que soporte HTML.",
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=[patient_user.email],
                )
                email.attach_alternative(html_content, "text/html")
                email.send(fail_silently=False)
                
                reminder_notification.status = Notification.Status.SENT
                reminder_notification.sent_at = timezone.now()
                reminder_count += 1
                
                logger.info(f"✓ Recordatorio enviado a {patient_user.email}")
                
            except Exception as e:
                reminder_notification.status = Notification.Status.FAILED
                reminder_notification.error_message = str(e)[:500]
                logger.error(f"✗ Error enviando recordatorio a {patient_user.email}: {str(e)}")
            
            finally:
                reminder_notification.save(update_fields=["status", "sent_at", "error_message"])
        
        logger.info(f"✓ Tarea completada: {reminder_count} recordatorio(s) enviado(s)")
        return {"sent": reminder_count}
        
    except Exception as e:
        logger.error(f"Error in send_appointment_reminders task: {str(e)}")
        raise
