"""Helpers shared across appointment-related views (and other apps, e.g. patient)
to avoid importing appointment.views (and its heavier dependency chain) from
elsewhere in the project.
"""
from django.db.models import F, Q
from django.db.models.functions import Greatest
from rest_framework.exceptions import ValidationError

from rules.models import EPSBudget


def _find_matching_eps_budget(eps, specialty, appt_date):
    """Returns the locked EPSBudget row matching eps/specialty/date, or None."""
    return (
        EPSBudget.objects.select_for_update()
        .filter(
            Q(specialty=specialty) | Q(specialty__isnull=True),
            eps=eps,
            period_start__lte=appt_date,
            period_end__gte=appt_date,
        )
        .first()
    )


def _check_eps_budget(patient, specialty, scheduled_at, exclude_appointment_id=None):
    """Returns the matching EPSBudget row (locked) so the caller can discount it, or None."""
    if not patient.eps:
        return None
    appt_date = scheduled_at.date()
    # select_for_update prevents two concurrent bookings from both passing the budget check
    budget = _find_matching_eps_budget(patient.eps, specialty, appt_date)
    if budget and budget.used_budget >= budget.total_budget:
        raise ValidationError(
            {"detail": "Tu EPS no tiene disponibilidad presupuestal para agendar esta cita."}
        )
    return budget


def _refund_eps_budget(patient, specialty, scheduled_at):
    """Gives back one unit of budget usage for a cancelled appointment, floored at 0."""
    if not patient.eps:
        return
    budget = _find_matching_eps_budget(patient.eps, specialty, scheduled_at.date())
    if budget is not None:
        EPSBudget.objects.filter(pk=budget.pk).update(
            used_budget=Greatest(F("used_budget") - 1, 0)
        )


def _transfer_eps_budget(patient, specialty, previous_scheduled_at, new_scheduled_at):
    """Moves the budget discount from the original period to the new one when a
    reschedule crosses budget-period boundaries. Raises if the new period has no
    remaining budget. No-ops if both dates fall in the same budget row."""
    if not patient.eps:
        return
    old_budget = _find_matching_eps_budget(patient.eps, specialty, previous_scheduled_at.date())
    new_budget = _find_matching_eps_budget(patient.eps, specialty, new_scheduled_at.date())

    if new_budget is None:
        return
    if old_budget is not None and old_budget.pk == new_budget.pk:
        return

    if new_budget.used_budget >= new_budget.total_budget:
        raise ValidationError(
            {"detail": "Tu EPS no tiene disponibilidad presupuestal para agendar esta cita."}
        )

    EPSBudget.objects.filter(pk=new_budget.pk).update(used_budget=F("used_budget") + 1)
    if old_budget is not None:
        EPSBudget.objects.filter(pk=old_budget.pk).update(
            used_budget=Greatest(F("used_budget") - 1, 0)
        )
