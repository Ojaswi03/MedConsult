from django.db import migrations


def _role_code(role):
    return {
        'hospital_owner': 'OWN', 'hospital_admin': 'ADM', 'doctor': 'DOC',
        'scheduler': 'SCH', 'billing_staff': 'BIL', 'compliance_officer': 'CMP',
        'clinical_staff': 'CLN', 'platform_owner': 'PLT', 'platform_admin': 'PLA',
    }.get(role, 'USR')


def backfill_hospital_user_ids(apps, schema_editor):
    OrganizationMembership = apps.get_model('accounts', 'OrganizationMembership')
    Organization = apps.get_model('accounts', 'Organization')

    for org in Organization.objects.all():
        memberships = OrganizationMembership.objects.filter(
            organization=org, hospital_user_id='',
        ).order_by('created_at')
        prefix = org.slug.replace('-', '')[:3].upper()
        count = OrganizationMembership.objects.filter(
            organization=org,
        ).exclude(hospital_user_id='').count()
        for m in memberships:
            count += 1
            m.hospital_user_id = f"{prefix}-{_role_code(m.role)}-{count:04d}"
            m.save(update_fields=['hospital_user_id'])


class Migration(migrations.Migration):
    dependencies = [
        ('accounts', '0021_membership_hospital_user_id'),
    ]

    operations = [
        migrations.RunPython(
            backfill_hospital_user_ids,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
