"""
Messaging domain permissions.
"""
from apps.accounts.permissions import (
    is_platform_staff, is_patient, is_doctor, has_org_role,
)


def can_view_conversation(user, conversation) -> bool:
    if is_platform_staff(user):
        return True
    return conversation.participants.filter(pk=user.pk).exists()


def can_send_message(user, conversation) -> bool:
    return can_view_conversation(user, conversation)


def can_start_conversation_with(user, other_user, organization) -> bool:
    """
    Doctors may only start direct chats with patients they have (or had)
    an active/completed appointment with. Platform staff are unrestricted.
    """
    if is_platform_staff(user):
        return True
    if is_doctor(user) and is_patient(other_user):
        from apps.scheduling.models import Appointment
        return Appointment.objects.filter(
            doctor__user=user, patient=other_user,
            organization=organization,
            status__in=['scheduled', 'completed'],
        ).exists()
    if is_patient(user) and is_doctor(other_user):
        from apps.scheduling.models import Appointment
        return Appointment.objects.filter(
            doctor__user=other_user, patient=user,
            organization=organization,
            status__in=['scheduled', 'completed'],
        ).exists()
    # Org staff within same org
    if organization:
        return (
            has_org_role(user, organization, [
                'hospital_owner', 'hospital_admin', 'scheduler',
                'billing_staff', 'clinical_staff', 'doctor',
            ])
            and has_org_role(other_user, organization, [
                'hospital_owner', 'hospital_admin', 'scheduler',
                'billing_staff', 'clinical_staff', 'doctor',
            ])
        )
    return False


def can_delete_message(user, message) -> bool:
    return is_platform_staff(user) or message.sender == user
