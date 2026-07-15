import math
from datetime import timedelta

from django.db.models import Q
from django.utils import timezone

from rules.models import EPSAppointmentLimit, EPSBudget, Period

DEFAULT_ALERT_THRESHOLD = 0.8


def period_bounds(scheduled_at, period):
    """Returns (start_date, end_date) for the week/month that contains scheduled_at."""
    appt_date = scheduled_at.date() if hasattr(scheduled_at, "date") else scheduled_at
    if period == Period.WEEKLY:
        monday = appt_date - timedelta(days=appt_date.weekday())
        return monday, monday + timedelta(days=6)
    else:
        first = appt_date.replace(day=1)
        if first.month == 12:
            last = first.replace(day=31)
        else:
            last = first.replace(month=first.month + 1) - timedelta(days=1)
        return first, last


def resolve_alert_threshold(threshold):
    try:
        threshold = float(threshold)
    except (TypeError, ValueError):
        return DEFAULT_ALERT_THRESHOLD
    if math.isnan(threshold) or math.isinf(threshold):
        return DEFAULT_ALERT_THRESHOLD
    if threshold < 0 or threshold > 1:
        return DEFAULT_ALERT_THRESHOLD
    return threshold


def get_eps_limit_alerts(threshold=DEFAULT_ALERT_THRESHOLD):
    from appointment.models import Appointment

    today = timezone.localdate()
    alerts = []
    for limit in EPSAppointmentLimit.objects.filter(active=True).select_related("eps", "specialty"):
        period_start, period_end = period_bounds(today, limit.period)
        appointments = Appointment.objects.filter(
            patient__eps=limit.eps,
            status__in=[Appointment.Status.CONFIRMED, Appointment.Status.PENDING],
            scheduled_at__date__gte=period_start,
            scheduled_at__date__lte=period_end,
        )
        if limit.specialty_id is not None:
            appointments = appointments.filter(specialty=limit.specialty)
        used = appointments.count()

        usage_ratio = used / limit.max_appointments if limit.max_appointments else 1.0
        if usage_ratio < threshold:
            continue

        alerts.append(
            {
                "type": "tope_citas",
                "eps": str(limit.eps),
                "specialty": limit.specialty.name if limit.specialty else None,
                "period": limit.period,
                "used": used,
                "max": limit.max_appointments,
                "usage_percent": round(usage_ratio * 100, 2),
                "level": "critical" if usage_ratio >= 1.0 else "warning",
            }
        )
    return alerts


def create_limit_alert_notifications(appointment):
    """Notifies every active superadmin when booking `appointment` pushes one of its
    EPS's active appointment limits to >= DEFAULT_ALERT_THRESHOLD usage.

    Dedup criteria: `Notification.limit` stores exactly which EPSAppointmentLimit
    triggered the alert, so two overlapping active limits for the same EPS (e.g. a
    general monthly limit with specialty=None and a specialty-specific weekly limit)
    each get their own, independent alert instead of one suppressing the other. We
    consider an alert already raised for a given superadmin when there is already a
    LIMIT_ALERT notification for that same user + limit whose appointment falls within
    the *same period window* of that limit (so a new period — e.g. the following month
    — still triggers a fresh alert once the threshold is crossed again).
    """
    from django.contrib.auth import get_user_model

    from appointment.models import Appointment
    from notifications.models import Notification

    patient = appointment.patient
    eps = patient.eps
    if not eps:
        return

    User = get_user_model()
    superadmins = list(User.objects.filter(rol=User.Role.SUPERADMIN, is_active=True))
    if not superadmins:
        return

    limits = EPSAppointmentLimit.objects.filter(
        Q(specialty=appointment.specialty) | Q(specialty__isnull=True),
        eps=eps,
        active=True,
    )

    for limit in limits:
        period_start, period_end = period_bounds(appointment.scheduled_at, limit.period)
        appointments_qs = Appointment.objects.filter(
            patient__eps=eps,
            status__in=[Appointment.Status.CONFIRMED, Appointment.Status.PENDING],
            scheduled_at__date__gte=period_start,
            scheduled_at__date__lte=period_end,
        )
        if limit.specialty_id is not None:
            appointments_qs = appointments_qs.filter(specialty=limit.specialty)
        used = appointments_qs.count()

        usage_ratio = used / limit.max_appointments if limit.max_appointments else 1.0
        if usage_ratio < DEFAULT_ALERT_THRESHOLD:
            continue

        for admin_user in superadmins:
            duplicate_exists = Notification.objects.filter(
                type=Notification.Type.LIMIT_ALERT,
                user=admin_user,
                limit=limit,
                appointment__scheduled_at__date__gte=period_start,
                appointment__scheduled_at__date__lte=period_end,
            ).exists()
            if duplicate_exists:
                continue

            Notification.objects.create(
                appointment=appointment,
                user=admin_user,
                limit=limit,
                type=Notification.Type.LIMIT_ALERT,
                channel="email",
                status=Notification.Status.PENDING,
            )


def get_eps_budget_alerts(threshold=DEFAULT_ALERT_THRESHOLD):
    today = timezone.localdate()
    alerts = []
    budgets = EPSBudget.objects.filter(
        period_start__lte=today, period_end__gte=today
    ).select_related("eps", "specialty")
    for budget in budgets:
        if budget.total_budget == 0:
            usage_ratio = 1.0
        else:
            usage_ratio = float(budget.used_budget) / float(budget.total_budget)

        if usage_ratio < threshold:
            continue

        alerts.append(
            {
                "type": "presupuesto",
                "eps": str(budget.eps),
                "specialty": budget.specialty.name if budget.specialty else None,
                "period": {
                    "start": budget.period_start.isoformat(),
                    "end": budget.period_end.isoformat(),
                },
                "used": float(budget.used_budget),
                "max": float(budget.total_budget),
                "usage_percent": round(usage_ratio * 100, 2),
                "level": "critical" if usage_ratio >= 1.0 else "warning",
            }
        )
    return alerts
