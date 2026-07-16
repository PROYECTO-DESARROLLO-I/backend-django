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


def send_appointment_rescheduled(appointment, previous_scheduled_at):
    """
    Notifica la reprogramación al paciente y al medico.
    """
    patient_user    = appointment.patient.user
    doctor_user     = appointment.doctor.user
    previous_local  = timezone.localtime(previous_scheduled_at)
    new_local       = timezone.localtime(appointment.scheduled_at)

    base_detail = (
        f"  Especialidad      : {appointment.specialty.name}\n"
        f"  Médico            : Dr(a). {doctor_user.nombre} {doctor_user.apellido}\n"
        f"  Fecha anterior    : {previous_local.strftime('%d/%m/%Y %H:%M')}\n"
        f"  Nueva fecha y hora: {new_local.strftime('%d/%m/%Y %H:%M')}\n"
        f"  Duración          : {appointment.duration_minutes} minutos\n"
    )
    if appointment.headquarters:
        base_detail += f"  Sede              : {appointment.headquarters.name}\n"
    base_detail += f"\nNúmero de cita: #{appointment.pk}\n"

    # Notificacion al paciente
    patient_notification = Notification.objects.create(
        appointment=appointment,
        user=patient_user,
        type=Notification.Type.RESCHEDULED,
        channel="email",
        status=Notification.Status.PENDING,
    )
    try:
        send_mail(
            subject=f"Reprogramación de cita médica — {appointment.specialty.name}",
            message=(
                f"Hola {patient_user.nombre},\n\n"
                f"Tu cita ha sido reprogramada:\n\n"
                + base_detail +
                f"\nSi tienes dudas sobre este cambio, comunícate con nosotros.\n\n"
                f"Salud AgendaX"
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[patient_user.email],
            fail_silently=False,
        )
        patient_notification.status = Notification.Status.SENT
        patient_notification.sent_at = timezone.now()
    except Exception:
        patient_notification.status = Notification.Status.FAILED
    finally:
        patient_notification.save(update_fields=["status", "sent_at"])

    # Notificacion al medico
    doctor_notification = Notification.objects.create(
        appointment=appointment,
        user=doctor_user,
        type=Notification.Type.RESCHEDULED,
        channel="email",
        status=Notification.Status.PENDING,
    )
    try:
        send_mail(
            subject=f"Cita reprogramada — {previous_local.strftime('%d/%m/%Y %H:%M')}",
            message=(
                f"Hola Dr(a). {doctor_user.nombre},\n\n"
                f"Una cita de tu agenda ha sido reprogramada:\n\n"
                f"  Paciente          : {patient_user.nombre} {patient_user.apellido}\n"
                + base_detail +
                f"\nEl horario anterior ha quedado disponible nuevamente.\n\n"
                f"Salud AgendaX"
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[doctor_user.email],
            fail_silently=False,
        )
        doctor_notification.status = Notification.Status.SENT
        doctor_notification.sent_at = timezone.now()
    except Exception:
        doctor_notification.status = Notification.Status.FAILED
    finally:
        doctor_notification.save(update_fields=["status", "sent_at"])


def send_appointment_cancelled(appointment, cancelled_by):
    """
    Notifica la cancelación al paciente y al médico.
    cancelled_by: instancia de User que realizó la cancelación.
    """
    patient_user = appointment.patient.user
    doctor_user  = appointment.doctor.user
    scheduled_local = timezone.localtime(appointment.scheduled_at)

    # ── Notificación al paciente ──────────────────────────────────────────
    patient_subject = f"Cancelación de cita médica — {appointment.specialty.name}"
    patient_message = (
        f"Hola {patient_user.nombre},\n\n"
        f"Tu cita ha sido cancelada:\n\n"
        f"  Especialidad : {appointment.specialty.name}\n"
        f"  Médico       : Dr(a). {doctor_user.nombre} {doctor_user.apellido}\n"
        f"  Fecha y hora : {scheduled_local.strftime('%d/%m/%Y %H:%M')}\n"
        f"  Número de cita: #{appointment.pk}\n\n"
        f"Si deseas agendar una nueva cita, puedes hacerlo desde la plataforma.\n\n"
        f"Salud AgendaX"
    )

    patient_notification = Notification.objects.create(
        appointment=appointment,
        user=patient_user,
        type=Notification.Type.CANCELLATION,
        channel="email",
        status=Notification.Status.PENDING,
    )

    try:
        send_mail(
            subject=patient_subject,
            message=patient_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[patient_user.email],
            fail_silently=False,
        )
        patient_notification.status = Notification.Status.SENT
        patient_notification.sent_at = timezone.now()
    except Exception:
        patient_notification.status = Notification.Status.FAILED
    finally:
        patient_notification.save(update_fields=["status", "sent_at"])

    # ── Notificación al médico ────────────────────────────────────────────
    doctor_subject = f"Cita cancelada — {scheduled_local.strftime('%d/%m/%Y %H:%M')}"
    doctor_message = (
        f"Hola Dr(a). {doctor_user.nombre},\n\n"
        f"La siguiente cita ha sido cancelada:\n\n"
        f"  Paciente     : {patient_user.nombre} {patient_user.apellido}\n"
        f"  Especialidad : {appointment.specialty.name}\n"
        f"  Fecha y hora : {scheduled_local.strftime('%d/%m/%Y %H:%M')}\n"
        f"  Número de cita: #{appointment.pk}\n\n"
        f"El horario ha quedado disponible nuevamente.\n\n"
        f"Salud AgendaX"
    )

    doctor_notification = Notification.objects.create(
        appointment=appointment,
        user=doctor_user,
        type=Notification.Type.CANCELLATION,
        channel="email",
        status=Notification.Status.PENDING,
    )

    try:
        send_mail(
            subject=doctor_subject,
            message=doctor_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[doctor_user.email],
            fail_silently=False,
        )
        doctor_notification.status = Notification.Status.SENT
        doctor_notification.sent_at = timezone.now()
    except Exception:
        doctor_notification.status = Notification.Status.FAILED
    finally:
        doctor_notification.save(update_fields=["status", "sent_at"])