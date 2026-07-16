from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone
from django.conf import settings as django_settings

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


def _already_alerted_limit(limit, period_label):
    """
    Evita enviar la misma alerta dos veces para el mismo tope en el mismo período.
    Retorna True si ya existe una notificación LIMIT_ALERT enviada para este limit.
    """
    return Notification.objects.filter(
        limit=limit,
        type=Notification.Type.LIMIT_ALERT,
        status=Notification.Status.SENT,
    ).exists()


def _already_alerted_budget(eps, specialty, period_start):
    """
    Evita duplicar alertas de presupuesto para el mismo período.
    """
    return Notification.objects.filter(
        type=Notification.Type.LIMIT_ALERT,
        status=Notification.Status.SENT,
        user__rol__in=["administrativo", "superadmin"],
        created_at__date__gte=period_start,
        # Identificamos por mensaje aproximado
    ).filter(
        user__notifications__isnull=False
    ).exists()


def _get_admin_users():
    """Retorna todos los usuarios administrativos y superadmin activos"""
    from user.models import User
    return User.objects.filter(
        rol__in=[User.Role.ADMINISTRATIVE, User.Role.SUPERADMIN],
        is_active=True,
    )


def check_and_send_limit_alert(appointment, warning_percent=80):
    """
    Verifica topes de EPS y presupuesto tras agendar una cita.
    Si el uso >= warning_percent, envía alerta a todos los administrativos.

    Llamar despues de crear la cita existosamente, fuera de la transacción.

    Args:
        appointment: instancia de Appointment recién creada
        warning_percent: umbral de advertencia (default 80%)
    """

    warning_percent = getattr(
        django_settings, 'EPS_ALERT_WARNING_PERCENT', 80
    )

    from rules.models import EPSAppointmentLimit, EPSBudget, Period
    from appointment.models import Appointment

    patient  = appointment.patient
    specialty = appointment.specialty

    if not patient.eps:
        return

    scheduled_at = appointment.scheduled_at

    # Verificar topes de citas por EPS 
    from django.db.models import Q
    from appointment.views import _period_bounds

    limits = EPSAppointmentLimit.objects.filter(
        Q(specialty=specialty) | Q(specialty__isnull=True),
        eps=patient.eps,
        active=True,
    )

    for limit in limits:
        period_start, period_end = _period_bounds(scheduled_at, limit.period)
        current_count = Appointment.objects.filter(
            patient__eps=patient.eps,
            specialty=specialty,
            status__in=[Appointment.Status.CONFIRMED, Appointment.Status.PENDING],
            scheduled_at__date__gte=period_start,
            scheduled_at__date__lte=period_end,
        ).count()

        usage_percent = (current_count / limit.max_appointments) * 100
        period_label  = "semana" if limit.period == Period.WEEKLY else "mes"

        if usage_percent >= warning_percent:
            if _already_alerted_limit(limit, period_label):
                continue  # ya fue alertado, no duplicar

            _send_limit_alert_email(
                limit=limit,
                eps_name=patient.eps.name,
                specialty_name=specialty.name,
                current_count=current_count,
                max_count=limit.max_appointments,
                usage_percent=usage_percent,
                period_label=period_label,
                alert_type="tope de citas",
            )

    # Verificar presupuesto EPS 
    from django.utils import timezone as tz
    appt_date = scheduled_at.date()

    budgets = EPSBudget.objects.filter(
        Q(specialty=specialty) | Q(specialty__isnull=True),
        eps=patient.eps,
        period_start__lte=appt_date,
        period_end__gte=appt_date,
    )

    for budget in budgets:
        if budget.total_budget == 0:
            continue

        usage_percent = (budget.used_budget / budget.total_budget) * 100

        if usage_percent >= warning_percent:
            _send_budget_alert_email(
                budget=budget,
                eps_name=patient.eps.name,
                specialty_name=specialty.name if budget.specialty else "todas las especialidades",
                used=budget.used_budget,
                total=budget.total_budget,
                usage_percent=usage_percent,
            )


def _send_limit_alert_email(limit, eps_name, specialty_name, current_count,
                             max_count, usage_percent, period_label, alert_type):
    """Envía email de alerta de tope a todos los administrativos y crea Notification."""
    admins = _get_admin_users()
    if not admins.exists():
        return

    subject = f"⚠️ Alerta de {alert_type} — {eps_name} / {specialty_name}"
    message = (
        f"ALERTA ADMINISTRATIVA — SaludAgendaX\n\n"
        f"Se ha alcanzado el umbral de advertencia para:\n\n"
        f"  EPS          : {eps_name}\n"
        f"  Especialidad : {specialty_name}\n"
        f"  Período      : Por {period_label}\n"
        f"  Uso actual   : {current_count} / {max_count} citas ({usage_percent:.1f}%)\n\n"
        f"El tope se alcanzará pronto. Revisa el dashboard administrativo "
        f"para tomar decisiones oportunas.\n\n"
        f"Salud AgendaX — Sistema de alertas automáticas"
    )

    for admin in admins:
        notification = Notification.objects.create(
            appointment=None,
            user=admin,
            limit=limit,
            type=Notification.Type.LIMIT_ALERT,
            channel="email",
            status=Notification.Status.PENDING,
        )
        try:
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[admin.email],
                fail_silently=False,
            )
            notification.status = Notification.Status.SENT
            notification.sent_at = timezone.now()
        except Exception:
            notification.status = Notification.Status.FAILED
        finally:
            notification.save(update_fields=["status", "sent_at"])


def _send_budget_alert_email(budget, eps_name, specialty_name, used, total, usage_percent):
    """Envía email de alerta de presupuesto a todos los administrativos."""
    admins = _get_admin_users()
    if not admins.exists():
        return

    subject = f"⚠️ Alerta de presupuesto — {eps_name} / {specialty_name}"
    message = (
        f"ALERTA ADMINISTRATIVA — SaludAgendaX\n\n"
        f"El presupuesto de la siguiente EPS está próximo a agotarse:\n\n"
        f"  EPS              : {eps_name}\n"
        f"  Especialidad     : {specialty_name}\n"
        f"  Período          : {budget.period_start} al {budget.period_end}\n"
        f"  Presupuesto usado: {used} / {total} citas ({usage_percent:.1f}%)\n\n"
        f"Si el presupuesto se agota, no se podrán agendar nuevas citas "
        f"para esta EPS. Revisa el dashboard para tomar decisiones oportunas.\n\n"
        f"Salud AgendaX — Sistema de alertas automáticas"
    )

    for admin in admins:
        notification = Notification.objects.create(
            appointment=None,
            user=admin,
            limit=None,
            type=Notification.Type.LIMIT_ALERT,
            channel="email",
            status=Notification.Status.PENDING,
        )
        try:
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[admin.email],
                fail_silently=False,
            )
            notification.status = Notification.Status.SENT
            notification.sent_at = timezone.now()
        except Exception:
            notification.status = Notification.Status.FAILED
        finally:
            notification.save(update_calls=["status", "sent_at"])