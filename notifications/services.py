from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from notifications.models import Notification


def send_appointment_confirmation(appointment):
    patient_user = appointment.patient.user
    doctor = appointment.doctor
    scheduled_local = timezone.localtime(appointment.scheduled_at)

    subject = f"Confirmación de cita médica — {appointment.specialty.name}"
    message = (
        f"Hola {patient_user.nombre},\n\n"
        f"Tu cita ha sido confirmada con los siguientes detalles:\n\n"
        f"  Especialidad : {appointment.specialty.name}\n"
        f"  Médico       : Dr(a). {doctor.user.nombre} {doctor.user.apellido}\n"
        f"  Fecha y hora : {scheduled_local.strftime('%d/%m/%Y %H:%M')}\n"
        f"  Duración     : {appointment.duration_minutes} minutos\n"
    )
    if appointment.headquarters:
        message += f"  Sede         : {appointment.headquarters.name}\n"
    message += (
        f"\nNúmero de cita: #{appointment.pk}\n\n"
        f"Si necesitas cancelar o reprogramar, comunícate con nosotros con anticipación.\n\n"
        f"Salud AgendaX"
    )

    notification = Notification.objects.create(
        appointment=appointment,
        user=patient_user,
        type=Notification.Type.CONFIRMATION,
        channel="email",
        status=Notification.Status.PENDING,
    )

    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[patient_user.email],
            fail_silently=False,
        )
        notification.status = Notification.Status.SENT
        notification.sent_at = timezone.now()
    except Exception:
        notification.status = Notification.Status.FAILED
    finally:
        notification.save(update_fields=["status", "sent_at"])
