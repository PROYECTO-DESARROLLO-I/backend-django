from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from notifications.models import Notification


def send_doctor_welcome(doctor):
    user = doctor.user
    specialties = ", ".join(s.name for s in doctor.specialties.all())

    subject = "Bienvenido a Salud AgendaX"
    message = (
        f"Hola Dr(a). {user.nombre} {user.apellido},\n\n"
        f"Tu cuenta ha sido creada exitosamente en Salud AgendaX.\n\n"
        f"  Correo          : {user.email}\n"
        f"  Registro médico : {doctor.register_number}\n"
        f"  Especialidad(es): {specialties}\n\n"
        f"Ya puedes iniciar sesión con tu correo y la contraseña asignada.\n\n"
        f"Salud AgendaX"
    )

    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )
    except Exception:
        # El registro no falla si el correo no se puede enviar (SMTP no configurado aún)
        pass


def send_password_reset_link(user, reset_url):
    subject = "Recuperación de contraseña — Salud AgendaX"
    message = (
        f"Hola {user.nombre},\n\n"
        f"Recibimos una solicitud para restablecer la contraseña de tu cuenta en Salud AgendaX.\n\n"
        f"Para continuar, ingresa al siguiente enlace:\n\n"
        f"  {reset_url}\n\n"
        f"Este enlace expira en 15 minutos.\n\n"
        f"Si no solicitaste este cambio, puedes ignorar este mensaje.\n\n"
        f"Salud AgendaX"
    )

    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )
    except Exception:
        # El envío no debe romper el flujo si el correo no se puede enviar
        pass


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
