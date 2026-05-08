"""
Payments domain permissions.
"""
from apps.accounts.permissions import (
    is_platform_staff, is_patient, is_doctor,
    can_manage_payments, can_refund_payment,
    can_view_org_payment_status, can_view_own_appointment_payment,
)


def can_view_payment(user, payment) -> bool:
    if is_platform_staff(user):
        return True
    patient = getattr(payment, 'patient', None)
    if is_patient(user) and patient == user:
        return True
    if is_doctor(user) and can_view_own_appointment_payment(user, payment):
        return True
    org = getattr(payment, 'organization', None)
    if org:
        return can_view_org_payment_status(user, org)
    return False


def can_initiate_refund(user, payment) -> bool:
    return can_refund_payment(user, payment)


def can_view_financial_report(user, organization) -> bool:
    return is_platform_staff(user) or can_manage_payments(user, organization)
