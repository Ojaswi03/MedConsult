from django.db import migrations
from django.utils import timezone


def create_default_orgs(apps, schema_editor):
    Organization = apps.get_model('accounts', 'Organization')
    OrganizationMembership = apps.get_model('accounts', 'OrganizationMembership')
    User = apps.get_model('accounts', 'User')

    platform_org, _ = Organization.objects.get_or_create(
        slug='medconsult-platform',
        defaults={
            'name': 'MedConsult Platform',
            'org_type': 'platform',
            'status': 'active',
        },
    )

    demo_clinic, _ = Organization.objects.get_or_create(
        slug='medconsult-demo-clinic',
        defaults={
            'name': 'MedConsult Demo Clinic',
            'org_type': 'clinic',
            'status': 'active',
        },
    )

    # Migrate legacy admin role → platform_owner
    User.objects.filter(role='admin').update(role='platform_owner')

    # platform_owner / platform_admin → membership in platform org
    for user in User.objects.filter(role__in=['platform_owner', 'platform_admin']):
        OrganizationMembership.objects.get_or_create(
            user=user,
            organization=platform_org,
            defaults={'role': user.role, 'is_active': True, 'accepted_at': timezone.now()},
        )

    # doctors → membership in demo clinic
    for user in User.objects.filter(role='doctor'):
        OrganizationMembership.objects.get_or_create(
            user=user,
            organization=demo_clinic,
            defaults={'role': 'doctor', 'is_active': True, 'accepted_at': timezone.now()},
        )

    # patients → NO membership (platform-wide)


def reverse_default_orgs(apps, schema_editor):
    Organization = apps.get_model('accounts', 'Organization')
    User = apps.get_model('accounts', 'User')
    Organization.objects.filter(
        slug__in=['medconsult-platform', 'medconsult-demo-clinic']
    ).delete()
    User.objects.filter(role='platform_owner').update(role='admin')


class Migration(migrations.Migration):
    dependencies = [
        ('accounts', '0017_add_organization_membership_invite'),
    ]

    operations = [
        migrations.RunPython(create_default_orgs, reverse_default_orgs),
    ]
