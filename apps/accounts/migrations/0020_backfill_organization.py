from django.db import migrations


def backfill_organization(apps, schema_editor):
    Organization = apps.get_model('accounts', 'Organization')
    OrganizationMembership = apps.get_model('accounts', 'OrganizationMembership')
    DoctorProfile = apps.get_model('accounts', 'DoctorProfile')
    Appointment = apps.get_model('scheduling', 'Appointment')
    Slot = apps.get_model('scheduling', 'Slot')
    AvailabilityWindow = apps.get_model('scheduling', 'AvailabilityWindow')
    Payment = apps.get_model('payments', 'Payment')
    Conversation = apps.get_model('messaging', 'Conversation')
    Referral = apps.get_model('scheduling', 'Referral')
    Prescription = apps.get_model('scheduling', 'Prescription')
    WaitlistEntry = apps.get_model('scheduling', 'WaitlistEntry')
    VideoRoom = apps.get_model('consultations', 'VideoRoom')

    try:
        demo_clinic = Organization.objects.get(slug='medconsult-demo-clinic')
    except Organization.DoesNotExist:
        return  # Skip on fresh install

    # DoctorProfile → org from membership
    for dp in DoctorProfile.objects.filter(organization__isnull=True):
        membership = OrganizationMembership.objects.filter(
            user=dp.user, role='doctor', is_active=True,
        ).first()
        if membership:
            dp.organization = membership.organization
            dp.save(update_fields=['organization'])
        else:
            dp.organization = demo_clinic
            dp.save(update_fields=['organization'])

    # Appointment → org from doctor profile
    for appt in Appointment.objects.filter(organization__isnull=True):
        dp = DoctorProfile.objects.filter(user=appt.doctor.user).first()
        appt.organization = dp.organization if (dp and dp.organization) else demo_clinic
        appt.save(update_fields=['organization'])

    # Slot → org from doctor profile
    for slot in Slot.objects.filter(organization__isnull=True):
        dp = DoctorProfile.objects.filter(user=slot.doctor.user).first()
        slot.organization = dp.organization if (dp and dp.organization) else demo_clinic
        slot.save(update_fields=['organization'])

    # AvailabilityWindow → org from doctor profile
    for aw in AvailabilityWindow.objects.filter(organization__isnull=True):
        dp = DoctorProfile.objects.filter(user=aw.doctor.user).first()
        aw.organization = dp.organization if (dp and dp.organization) else demo_clinic
        aw.save(update_fields=['organization'])

    # Payment → from appointment
    for payment in Payment.objects.filter(organization__isnull=True):
        appt = payment.appointment
        payment.organization = appt.organization if (appt and appt.organization) else demo_clinic
        payment.save(update_fields=['organization'])

    # Conversation → from appointment if linked, else demo clinic
    for conv in Conversation.objects.filter(organization__isnull=True):
        if conv.appointment and conv.appointment.organization:
            conv.organization = conv.appointment.organization
        else:
            conv.organization = demo_clinic
        conv.save(update_fields=['organization'])

    # Referral → from referring doctor
    for ref in Referral.objects.filter(organization__isnull=True):
        dp = DoctorProfile.objects.filter(user=ref.referring_doctor.user).first()
        ref.organization = dp.organization if (dp and dp.organization) else demo_clinic
        ref.save(update_fields=['organization'])

    # Prescription → from appointment
    for rx in Prescription.objects.filter(organization__isnull=True):
        rx.organization = rx.appointment.organization if rx.appointment.organization else demo_clinic
        rx.save(update_fields=['organization'])

    # WaitlistEntry → from doctor profile
    for we in WaitlistEntry.objects.filter(organization__isnull=True):
        dp = DoctorProfile.objects.filter(user=we.doctor.user).first()
        we.organization = dp.organization if (dp and dp.organization) else demo_clinic
        we.save(update_fields=['organization'])

    # VideoRoom → from appointment
    for vr in VideoRoom.objects.filter(organization__isnull=True):
        vr.organization = vr.appointment.organization if vr.appointment.organization else demo_clinic
        vr.save(update_fields=['organization'])


def reverse_backfill(apps, schema_editor):
    pass  # Irreversible


class Migration(migrations.Migration):
    dependencies = [
        ('accounts', '0019_add_organization_fk'),
        ('scheduling', '0020_add_organization_fk'),
        ('payments', '0002_add_organization_fk'),
        ('messaging', '0005_add_organization_fk'),
        ('consultations', '0002_add_organization_fk'),
        ('adminpanel', '0004_add_organization_fk'),
    ]

    operations = [
        migrations.RunPython(backfill_organization, reverse_backfill),
    ]
