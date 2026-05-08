"""
Scheduling domain permissions.
"""
from apps.accounts.permissions import (
    is_platform_staff, is_doctor, is_patient,
    can_manage_org_appointments, can_manage_own_appointment,
    can_access_patient_phi, can_view_health_record, has_org_role,
)


def can_view_slot(user, slot) -> bool:
    """Slots are publicly visible (browsing doctors)."""
    return bool(user and getattr(user, 'is_authenticated', False))


def can_book_slot(user, slot) -> bool:
    return is_patient(user)


def can_block_slot(user, slot) -> bool:
    """Doctor blocks their own slot; org schedulers/admins can block any slot in their org."""
    if is_platform_staff(user):
        return True
    if is_doctor(user):
        return (
            hasattr(slot, 'availability_window')
            and hasattr(slot.availability_window, 'doctor')
            and slot.availability_window.doctor.user == user
        )
    org = getattr(slot, 'organization', None)
    if org:
        return has_org_role(user, org, ['hospital_owner', 'hospital_admin', 'scheduler'])
    return False


def can_cancel_appointment(user, appointment) -> bool:
    """Patient cancels own; doctor cancels own; org schedulers/admins cancel org-wide."""
    if is_platform_staff(user):
        return True
    if is_patient(user) and appointment.patient == user:
        return True
    if can_manage_own_appointment(user, appointment):
        return True
    org = getattr(appointment, 'organization', None)
    if org:
        return has_org_role(user, org, ['hospital_owner', 'hospital_admin', 'scheduler'])
    return False


def can_view_appointment(user, appointment) -> bool:
    if is_platform_staff(user):
        return True
    if is_patient(user) and appointment.patient == user:
        return True
    if can_manage_own_appointment(user, appointment):
        return True
    org = getattr(appointment, 'organization', None)
    if org:
        return has_org_role(
            user, org,
            ['hospital_owner', 'hospital_admin', 'scheduler', 'clinical_staff'],
        )
    return False


def can_write_prescription(user, appointment) -> bool:
    return can_manage_own_appointment(user, appointment)


def can_view_prescription(user, prescription) -> bool:
    if is_platform_staff(user):
        return True
    patient = getattr(prescription, 'patient', None)
    if is_patient(user) and patient == user:
        return True
    appointment = getattr(prescription, 'appointment', None)
    if appointment:
        return can_manage_own_appointment(user, appointment)
    return False
