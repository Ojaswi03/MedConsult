import uuid
from django.utils.text import slugify
from django.db import transaction
from apps.accounts.models import User, Organization, OrganizationMembership
from apps.accounts.tasks import send_verification_email_task


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

    OrganizationMembership.objects.create(
        user=user,
        organization=org,
        role='hospital_owner',
        is_active=True,
    )

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
