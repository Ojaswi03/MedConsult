"""
Permission helpers for MedConsult multi-tenant access control.

Three tiers:
  Tier 1 — Global account checks (User.role)
  Tier 2 — Org membership checks (OrganizationMembership.role)
  Tier 3 — Action checks (combine tier 1 + 2 + object relationships)

All helpers fail closed: unauthenticated / None users return False.
"""


# ── Tier 1: Global account checks ────────────────────────────────────────────

def is_platform_owner(user) -> bool:
    return bool(
        user and getattr(user, 'is_authenticated', False)
        and user.role == 'platform_owner'
    )


def is_platform_staff(user) -> bool:
    return bool(
        user and getattr(user, 'is_authenticated', False)
        and user.role in ('platform_owner', 'platform_admin')
    )


def is_doctor(user) -> bool:
    return bool(
        user and getattr(user, 'is_authenticated', False)
        and user.role == 'doctor'
    )


def is_patient(user) -> bool:
    return bool(
        user and getattr(user, 'is_authenticated', False)
        and user.role == 'patient'
    )


def is_org_user(user) -> bool:
    return bool(
        user and getattr(user, 'is_authenticated', False)
        and user.role == 'org_user'
    )


# ── Tier 2: Org membership checks ────────────────────────────────────────────

def get_membership(user, organization):
    """Return active OrganizationMembership or None."""
    if not user or not getattr(user, 'is_authenticated', False):
        return None
    from apps.accounts.models import OrganizationMembership
    return OrganizationMembership.objects.filter(
        user=user, organization=organization, is_active=True,
    ).first()


def has_org_role(user, organization, allowed_roles) -> bool:
    """True if user has an active membership with one of the allowed roles."""
    if not user or not getattr(user, 'is_authenticated', False):
        return False
    from apps.accounts.models import OrganizationMembership
    return OrganizationMembership.objects.filter(
        user=user, organization=organization,
        role__in=allowed_roles, is_active=True,
    ).exists()


def get_user_organizations(user):
    """Return queryset of organizations where user has an active membership."""
    if not user or not getattr(user, 'is_authenticated', False):
        from apps.accounts.models import Organization
        return Organization.objects.none()
    from apps.accounts.models import Organization, OrganizationMembership
    org_ids = OrganizationMembership.objects.filter(
        user=user, is_active=True,
    ).values_list('organization_id', flat=True)
    return Organization.objects.filter(id__in=org_ids)


def has_any_elevated_membership(user) -> bool:
    """
    True if user has any active org membership with an elevated role.
    Used by 2FA middleware — does NOT depend on selected org.
    """
    if not user or not getattr(user, 'is_authenticated', False):
        return False
    ELEVATED = [
        'hospital_owner', 'hospital_admin', 'scheduler',
        'billing_staff', 'compliance_officer', 'clinical_staff', 'doctor',
    ]
    from apps.accounts.models import OrganizationMembership
    return OrganizationMembership.objects.filter(
        user=user, is_active=True, role__in=ELEVATED,
    ).exists()


# ── Tier 3: Action checks ─────────────────────────────────────────────────────

def can_approve_organization(user) -> bool:
    return is_platform_staff(user)


def can_suspend_organization(user) -> bool:
    return is_platform_staff(user)


def can_edit_organization_profile(user, organization) -> bool:
    return is_platform_staff(user) or has_org_role(
        user, organization, ['hospital_owner', 'hospital_admin'],
    )


def can_manage_staff(user, organization) -> bool:
    return is_platform_staff(user) or has_org_role(
        user, organization, ['hospital_owner', 'hospital_admin'],
    )


def can_invite_staff(user, organization) -> bool:
    return can_manage_staff(user, organization)


def get_invitable_roles(user, organization) -> list:
    """Return roles this user is allowed to grant via invite."""
    if is_platform_staff(user):
        from apps.accounts.models import OrganizationMembership
        return [r for r, _ in OrganizationMembership.ROLE_CHOICES]
    if has_org_role(user, organization, ['hospital_owner']):
        return [
            'hospital_admin', 'doctor', 'scheduler',
            'billing_staff', 'compliance_officer', 'clinical_staff',
        ]
    if has_org_role(user, organization, ['hospital_admin']):
        return ['doctor', 'scheduler', 'billing_staff', 'clinical_staff']
    return []


def can_manage_org_appointments(user, organization) -> bool:
    """Org-wide appointment management — doctors excluded (they use can_manage_own_appointment)."""
    return is_platform_staff(user) or has_org_role(
        user, organization,
        ['hospital_owner', 'hospital_admin', 'scheduler'],
    )


def can_manage_own_appointment(user, appointment) -> bool:
    """Doctor can manage only their own appointments."""
    return bool(
        is_doctor(user)
        and hasattr(appointment, 'doctor')
        and hasattr(appointment.doctor, 'user')
        and appointment.doctor.user == user
    )


def can_view_org_payment_status(user, organization) -> bool:
    return is_platform_staff(user) or has_org_role(
        user, organization,
        ['hospital_owner', 'hospital_admin', 'scheduler', 'billing_staff'],
    )


def can_view_own_appointment_payment(user, payment) -> bool:
    return bool(
        is_doctor(user)
        and hasattr(payment, 'appointment')
        and hasattr(payment.appointment, 'doctor')
        and hasattr(payment.appointment.doctor, 'user')
        and payment.appointment.doctor.user == user
    )


def can_manage_payments(user, organization) -> bool:
    return is_platform_staff(user) or has_org_role(
        user, organization, ['hospital_owner', 'billing_staff'],
    )


def can_refund_payment(user, payment) -> bool:
    if is_platform_staff(user):
        return True
    org = getattr(payment, 'organization', None)
    if not org:
        return False
    return has_org_role(user, org, ['hospital_owner', 'billing_staff'])


def can_view_audit_logs(user, organization) -> bool:
    return is_platform_staff(user) or has_org_role(
        user, organization, ['hospital_owner', 'compliance_officer'],
    )


def can_access_patient_phi(user, patient, organization) -> bool:
    """
    Doctor can access patient PHI only if they have an active org membership
    AND an active/completed appointment with that patient in this org,
    OR a health record was explicitly shared with them.
    """
    if not is_doctor(user):
        return False
    if not has_org_role(user, organization, ['doctor']):
        return False
    from apps.scheduling.models import Appointment
    has_appointment = Appointment.objects.filter(
        doctor__user=user, patient=patient,
        organization=organization,
        status__in=['scheduled', 'completed'],
    ).exists()
    if has_appointment:
        return True
    from apps.scheduling.models import HealthRecordShare
    return HealthRecordShare.objects.filter(
        record__patient=patient,
        shared_with_doctor=user,
        revoked_at__isnull=True,
    ).exists()


def can_view_health_record(user, record) -> bool:
    """Fails closed. Platform staff do NOT have access until break-glass is implemented."""
    if record.patient == user:
        return True
    if is_doctor(user):
        from apps.scheduling.models import HealthRecordShare, Appointment
        if HealthRecordShare.objects.filter(
            record=record,
            shared_with_doctor=user,
            revoked_at__isnull=True,
        ).exists():
            from apps.accounts.models import OrganizationMembership
            return OrganizationMembership.objects.filter(
                user=user, is_active=True, role='doctor',
            ).exists()
        return Appointment.objects.filter(
            doctor__user=user, patient=record.patient,
            status__in=['scheduled', 'completed'],
        ).exists()
    return False


def can_break_glass_access_phi(user, record, reason) -> bool:
    """Stub — returns False until break-glass workflow is implemented."""
    return False
