"""
Admin panel domain permissions.
"""
from apps.accounts.permissions import (
    is_platform_staff,
    can_approve_organization, can_suspend_organization,
    can_edit_organization_profile, can_manage_staff,
    can_view_audit_logs,
)


def can_access_admin_panel(user) -> bool:
    return is_platform_staff(user)


def can_view_org_list(user) -> bool:
    return is_platform_staff(user)


def can_approve_org(user) -> bool:
    return can_approve_organization(user)


def can_suspend_org(user) -> bool:
    return can_suspend_organization(user)


def can_edit_org(user, organization) -> bool:
    return can_edit_organization_profile(user, organization)


def can_manage_org_staff(user, organization) -> bool:
    return can_manage_staff(user, organization)


def can_view_logs(user, organization) -> bool:
    return can_view_audit_logs(user, organization)


def can_export_data(user) -> bool:
    """CSV / data exports require platform staff."""
    return is_platform_staff(user)


def can_verify_doctor(user) -> bool:
    return is_platform_staff(user)
