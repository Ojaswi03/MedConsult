"""
Organization context resolution for requests.
Separates org resolution from permission checks.
"""
from dataclasses import dataclass
from typing import Optional


@dataclass
class OrgContext:
    organization: Optional[object] = None   # Organization | None
    membership: Optional[object] = None     # OrganizationMembership | None
    is_platform_scope: bool = False
    source: str = 'none'  # 'url' | 'session' | 'single_membership' | 'none'


def get_selected_organization(request) -> OrgContext:
    """
    Resolve the active organization for this request.

    Priority:
    1. URL kwarg org_slug (user must have active membership, or be platform staff)
    2. session['active_organization_id']
    3. User's single active membership org
    4. None (platform staff get is_platform_scope=True; patients get empty context)
    """
    from apps.accounts.models import Organization, OrganizationMembership
    from apps.accounts.permissions import is_platform_staff

    user = request.user
    if not user or not user.is_authenticated:
        return OrgContext()

    _is_platform = is_platform_staff(user)

    # 1. URL kwarg org_slug
    org_slug = None
    if getattr(request, 'resolver_match', None):
        org_slug = request.resolver_match.kwargs.get('org_slug')

    if org_slug:
        try:
            org = Organization.objects.get(slug=org_slug, status='active')
        except Organization.DoesNotExist:
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied("Organization not found or inactive.")
        membership = OrganizationMembership.objects.filter(
            user=user, organization=org, is_active=True,
        ).first()
        if not _is_platform and not membership:
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied("You do not have access to this organization.")
        return OrgContext(
            organization=org, membership=membership,
            is_platform_scope=_is_platform, source='url',
        )

    # 2. Session
    session_org_id = request.session.get('active_organization_id')
    if session_org_id:
        try:
            org = Organization.objects.get(id=session_org_id, status='active')
            membership = OrganizationMembership.objects.filter(
                user=user, organization=org, is_active=True,
            ).first()
            if membership or _is_platform:
                return OrgContext(
                    organization=org, membership=membership,
                    is_platform_scope=_is_platform, source='session',
                )
        except Organization.DoesNotExist:
            pass

    # 3. Single active membership
    memberships = list(
        OrganizationMembership.objects.filter(
            user=user, is_active=True,
        ).select_related('organization')
    )
    if len(memberships) == 1:
        m = memberships[0]
        return OrgContext(
            organization=m.organization, membership=m,
            is_platform_scope=_is_platform, source='single_membership',
        )

    # 4. Fallback
    return OrgContext(is_platform_scope=_is_platform, source='none')
