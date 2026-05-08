"""
Query scoping utilities for multi-tenant data isolation.

Core rule: organization=None fails closed (returns queryset.none())
unless platform access is explicitly proven via is_platform_staff(user).
"""
from apps.accounts.permissions import is_platform_staff


def scope_to_org(queryset, organization, user=None):
    """
    Scope a queryset to an organization.

    - If organization is provided: filter queryset by organization.
    - If organization is None and user is platform staff: return unscoped queryset.
    - If organization is None and user is not platform staff: return empty queryset.
    """
    if organization is None:
        if user is not None and is_platform_staff(user):
            return queryset
        return queryset.none()
    return queryset.filter(organization=organization)
