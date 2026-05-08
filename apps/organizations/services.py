import uuid
from django.utils.text import slugify
from django.db import transaction
from apps.accounts.models import User, Organization, OrganizationMembership
from apps.accounts.tasks import send_verification_email_task

_ROLE_CODE = {
    'hospital_owner': 'OWN',
    'hospital_admin': 'ADM',
    'doctor': 'DOC',
    'scheduler': 'SCH',
    'billing_staff': 'BIL',
    'compliance_officer': 'CMP',
    'clinical_staff': 'CLN',
    'platform_owner': 'PLT',
    'platform_admin': 'PLA',
}


def generate_hospital_user_id(organization, role: str) -> str:
    """
    Returns a unique ID like CIT-DOC-0007 scoped to the given organization.
    Prefix = first 3 chars of slug (uppercased, no hyphens).
    Sequence = existing membership count in org + 1.
    """
    prefix = organization.slug.replace('-', '')[:3].upper()
    role_code = _ROLE_CODE.get(role, 'USR')
    count = OrganizationMembership.objects.filter(organization=organization).count() + 1
    return f"{prefix}-{role_code}-{count:04d}"


@transaction.atomic
def create_membership(user, organization, role: str, invited_by=None, accepted_at=None):
    """
    Create (or reactivate) a membership with auto-generated hospital_user_id.
    Also creates ProviderOrganizationProfile if role == 'doctor'.
    """
    from apps.accounts.models import ProviderOrganizationProfile
    from django.utils import timezone

    existing = OrganizationMembership.objects.filter(
        user=user, organization=organization,
    ).first()

    if existing:
        existing.role = role
        existing.is_active = True
        if not existing.hospital_user_id:
            existing.hospital_user_id = generate_hospital_user_id(organization, role)
        existing.save(update_fields=['role', 'is_active', 'hospital_user_id'])
        membership = existing
    else:
        hospital_user_id = generate_hospital_user_id(organization, role)
        membership = OrganizationMembership.objects.create(
            user=user,
            organization=organization,
            role=role,
            is_active=True,
            hospital_user_id=hospital_user_id,
            invited_by=invited_by,
            invited_at=timezone.now() if invited_by else None,
            accepted_at=accepted_at,
        )

    if role == 'doctor':
        ProviderOrganizationProfile.objects.get_or_create(
            doctor=user,
            organization=organization,
            defaults={
                'membership': membership,
                'provider_id': membership.hospital_user_id,
                'specialization': getattr(
                    getattr(user, 'doctorprofile', None), 'specialization', ''
                ) or '',
            },
        )

    return membership


@transaction.atomic
def register_organization(account_data: dict, org_data: dict):
    """Create org_user + pending Organization + hospital_owner membership."""
    user = User.objects.create_user(
        username=account_data['email'].split('@')[0] + '_' + uuid.uuid4().hex[:6],
        email=account_data['email'].lower(),
        password=account_data['password1'],
        first_name=account_data['first_name'],
        last_name=account_data['last_name'],
        role='org_user',
        is_email_verified=False,
    )

    base_slug = slugify(org_data['org_name'])
    slug = base_slug
    counter = 1
    while Organization.objects.filter(slug=slug).exists():
        slug = f'{base_slug}-{counter}'
        counter += 1

    org = Organization.objects.create(
        name=org_data['org_name'],
        slug=slug,
        org_type=org_data['org_type'],
        status='pending',
        address=org_data.get('address', ''),
        phone=org_data.get('phone', ''),
        website=org_data.get('website', ''),
        created_by=user,
    )
    if org_data.get('logo'):
        org.logo = org_data['logo']
        org.save(update_fields=['logo'])

    create_membership(user=user, organization=org, role='hospital_owner')

    send_verification_email_task.delay(user.id)
    _notify_platform_owners_new_org(org)
    return user, org


def _notify_platform_owners_new_org(org: Organization) -> None:
    from apps.accounts.services import create_notification
    for owner in User.objects.filter(role='platform_owner', is_active=True):
        create_notification(
            owner,
            'org_pending',
            f"New org pending: {org.name}",
            f"{org.name} ({org.get_org_type_display()}) has submitted a registration and is awaiting review.",
            link='/internal/organizations/',
        )
