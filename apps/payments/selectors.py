"""
Payments selectors for read operations.
"""
from django.db.models import Q, Sum
from apps.accounts.query_utils import scope_to_org


def get_payments_for_org(organization, user=None):
    """Payments scoped to an org. Fails closed if org is None and user is not platform staff."""
    from .models import Payment
    qs = Payment.objects.select_related('appointment', 'patient')
    return scope_to_org(qs, organization, user).order_by('-created_at')


def get_payment_for_appointment(appointment):
    """Get payment for a single appointment regardless of org (caller must verify access)."""
    from .models import Payment
    return Payment.objects.filter(appointment=appointment).first()


def get_patient_payments(patient):
    """All payments for a patient — scoped by patient FK, no org filter needed."""
    from .models import Payment
    return Payment.objects.filter(patient=patient).select_related(
        'appointment',
    ).order_by('-created_at')


def get_revenue_for_org(organization, user=None):
    """Total revenue (succeeded payments) for an org."""
    from .models import Payment
    qs = Payment.objects.filter(status='succeeded')
    scoped = scope_to_org(qs, organization, user)
    return scoped.aggregate(total=Sum('amount'))['total'] or 0


def get_refunds_for_org(organization, user=None):
    """Refunds scoped to an org via payment FK."""
    from .models import Refund
    qs = Refund.objects.select_related('payment').filter(
        payment__organization=organization,
    )
    if organization is None:
        from apps.accounts.permissions import is_platform_staff
        if user is None or not is_platform_staff(user):
            return Refund.objects.none()
        return qs
    return qs.order_by('-created_at')
