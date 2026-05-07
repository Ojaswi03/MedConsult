"""
Celery tasks for scheduling app - appointment reminders and notifications.
"""
from celery import shared_task
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.utils import timezone
from datetime import timedelta


@shared_task(bind=True, max_retries=3)
def send_appointment_reminder_email(self, appointment_id, reminder_type='24h'):
    """
    Send appointment reminder email.
    reminder_type: '24h' for 24-hour reminder, '1h' for 1-hour reminder
    """
    from .models import Appointment

    try:
        appointment = Appointment.objects.select_related(
            'patient', 'doctor', 'doctor__user', 'slot'
        ).get(id=appointment_id)

        if appointment.status != 'scheduled':
            return f"Appointment {appointment_id} is not scheduled, skipping reminder"

        # Send to patient
        subject = f"Reminder: Appointment {'tomorrow' if reminder_type == '24h' else 'in 1 hour'}"
        html_message = render_to_string('scheduling/emails/appointment_reminder.html', {
            'appointment': appointment,
            'reminder_type': reminder_type,
            'is_patient': True,
        })
        plain_message = f"""
Hi {appointment.patient.first_name or appointment.patient.username},

This is a reminder for your upcoming appointment:

Doctor: Dr. {appointment.doctor.user.get_display_name()}
Date: {appointment.start_datetime.strftime('%B %d, %Y')}
Time: {appointment.start_datetime.strftime('%I:%M %p')}
Type: {appointment.slot.get_appointment_type_display()}

{'Your appointment is tomorrow.' if reminder_type == '24h' else 'Your appointment starts in 1 hour.'}

Best regards,
The MedConsult Team
        """

        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[appointment.patient.email],
            html_message=html_message,
            fail_silently=False,
        )

        return f"Reminder sent to {appointment.patient.email} for appointment {appointment_id}"

    except Appointment.DoesNotExist:
        return f"Appointment {appointment_id} not found"
    except Exception as exc:
        self.retry(exc=exc, countdown=60)


@shared_task
def schedule_appointment_reminders():
    """
    Periodic task to schedule reminders for upcoming appointments.
    Run this every 15 minutes via Celery Beat.
    """
    from .models import Appointment

    now = timezone.now()

    # Find appointments in 24 hours (with 15 min window)
    start_24h = now + timedelta(hours=23, minutes=45)
    end_24h = now + timedelta(hours=24, minutes=15)

    appointments_24h = Appointment.objects.filter(
        status='scheduled',
        slot__start_datetime__gte=start_24h,
        slot__start_datetime__lte=end_24h,
    ).values_list('id', flat=True)

    for appointment_id in appointments_24h:
        send_appointment_reminder_email.delay(appointment_id, '24h')

    # Find appointments in 1 hour (with 15 min window)
    start_1h = now + timedelta(minutes=45)
    end_1h = now + timedelta(hours=1, minutes=15)

    appointments_1h = Appointment.objects.filter(
        status='scheduled',
        slot__start_datetime__gte=start_1h,
        slot__start_datetime__lte=end_1h,
    ).values_list('id', flat=True)

    for appointment_id in appointments_1h:
        send_appointment_reminder_email.delay(appointment_id, '1h')

    # SMS reminders for patients with phone_notifications=True
    phone_notif_24h = Appointment.objects.filter(
        status='scheduled',
        slot__start_datetime__gte=start_24h,
        slot__start_datetime__lte=end_24h,
        patient__phone_notifications=True,
    ).values_list('id', flat=True)
    for appointment_id in phone_notif_24h:
        send_sms_reminder.delay(appointment_id, '24h')

    phone_notif_1h = Appointment.objects.filter(
        status='scheduled',
        slot__start_datetime__gte=start_1h,
        slot__start_datetime__lte=end_1h,
        patient__phone_notifications=True,
    ).values_list('id', flat=True)
    for appointment_id in phone_notif_1h:
        send_sms_reminder.delay(appointment_id, '1h')

    return f"Scheduled {len(appointments_24h)} 24h reminders and {len(appointments_1h)} 1h reminders"


@shared_task(bind=True, max_retries=3)
def send_sms_reminder(self, appointment_id, reminder_type='1h'):
    """
    Send SMS reminder for appointment using Twilio.
    """
    from .models import Appointment

    if not all([settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN, settings.TWILIO_PHONE_NUMBER]):
        return "Twilio not configured, skipping SMS"

    try:
        from twilio.rest import Client

        appointment = Appointment.objects.select_related(
            'patient', 'doctor', 'doctor__user'
        ).get(id=appointment_id)

        if appointment.status != 'scheduled':
            return f"Appointment {appointment_id} is not scheduled"

        if not appointment.patient.phone:
            return f"Patient has no phone number"

        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)

        message_body = (
            f"MedConsult Reminder: Your appointment with Dr. {appointment.doctor.user.get_display_name()} "
            f"is {'tomorrow' if reminder_type == '24h' else 'in 1 hour'} at {appointment.start_datetime.strftime('%I:%M %p')}."
        )

        message = client.messages.create(
            body=message_body,
            from_=settings.TWILIO_PHONE_NUMBER,
            to=appointment.patient.phone
        )

        return f"SMS sent: {message.sid}"

    except Appointment.DoesNotExist:
        return f"Appointment {appointment_id} not found"
    except Exception as exc:
        self.retry(exc=exc, countdown=60)


@shared_task(bind=True, max_retries=3)
def send_appointment_confirmation_email(self, appointment_id):
    """
    Send appointment confirmation email after booking.
    """
    from .models import Appointment

    try:
        appointment = Appointment.objects.select_related(
            'patient', 'doctor', 'doctor__user', 'slot'
        ).get(id=appointment_id)

        subject = "Appointment Confirmed - MedConsult"
        html_message = render_to_string('scheduling/emails/appointment_confirmation.html', {
            'appointment': appointment,
        })
        plain_message = f"""
Hi {appointment.patient.first_name or appointment.patient.username},

Your appointment has been confirmed!

Doctor: Dr. {appointment.doctor.user.get_display_name()}
Date: {appointment.start_datetime.strftime('%B %d, %Y')}
Time: {appointment.start_datetime.strftime('%I:%M %p')}
Type: {appointment.slot.get_appointment_type_display()}

Best regards,
The MedConsult Team
        """

        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[appointment.patient.email],
            html_message=html_message,
            fail_silently=False,
        )

        return f"Confirmation sent for appointment {appointment_id}"

    except Appointment.DoesNotExist:
        return f"Appointment {appointment_id} not found"
    except Exception as exc:
        self.retry(exc=exc, countdown=60)


@shared_task(bind=True, max_retries=3)
def send_sms_appointment_confirmation(self, appointment_id):
    """
    Send SMS confirmation when an appointment is booked.
    """
    from .models import Appointment

    if not all([settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN, settings.TWILIO_PHONE_NUMBER]):
        return "Twilio not configured, skipping SMS"

    try:
        from twilio.rest import Client

        appointment = Appointment.objects.select_related(
            'patient', 'doctor', 'doctor__user'
        ).get(id=appointment_id)

        if not appointment.patient.phone:
            return "Patient has no phone number"

        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)

        message_body = (
            f"MedConsult: Your appointment with Dr. {appointment.doctor.user.get_display_name()} "
            f"is confirmed for {appointment.start_datetime.strftime('%B %d at %I:%M %p')}."
        )

        message = client.messages.create(
            body=message_body,
            from_=settings.TWILIO_PHONE_NUMBER,
            to=appointment.patient.phone
        )

        return f"SMS confirmation sent: {message.sid}"

    except Appointment.DoesNotExist:
        return f"Appointment {appointment_id} not found"
    except Exception as exc:
        self.retry(exc=exc, countdown=60)


@shared_task
def notify_waitlist_for_doctor(doctor_id):
    """Notify waitlisted patients when slots become available for a doctor."""
    from .models import WaitlistEntry, Slot
    from apps.accounts.services import create_notification
    from apps.accounts.models import DoctorProfile

    try:
        doctor = DoctorProfile.objects.get(id=doctor_id)
    except DoctorProfile.DoesNotExist:
        return "Doctor not found"

    has_slots = Slot.objects.filter(
        doctor=doctor,
        is_booked=False,
        is_blocked=False,
        start_datetime__gt=timezone.now()
    ).exists()

    if not has_slots:
        return "No available slots"

    entries = WaitlistEntry.objects.filter(doctor=doctor, is_notified=False).select_related('patient')
    count = 0
    for entry in entries:
        create_notification(
            entry.patient, 'waitlist_slot_available',
            f"Slot available: Dr. {doctor.user.get_display_name()}",
            "A slot is now available. Book before it's gone!",
            link=f"/patient/doctors/{doctor.id}/"
        )
        entry.is_notified = True
        entry.notified_at = timezone.now()
        entry.save()
        count += 1
    return f"Notified {count} waitlisted patients"


@shared_task
def extend_slots_for_all_doctors():
    """Nightly task to extend slots 60 days out for all active doctors."""
    from apps.accounts.models import DoctorProfile
    from .services import generate_slots_for_doctor

    doctors = DoctorProfile.objects.filter(
        verification_status='verified',
        user__is_active=True
    )
    total = 0
    for doctor in doctors:
        slots = generate_slots_for_doctor(doctor, days_ahead=60)
        total += len(slots)
    return f"Extended slots for {doctors.count()} doctors, created {total} new slots"


@shared_task
def mark_completed_appointments():
    """Mark scheduled appointments as completed if their end_datetime has passed."""
    from .models import Appointment
    now = timezone.now()
    count = Appointment.objects.filter(
        status='scheduled',
        booking_status='confirmed',
        slot__end_datetime__lt=now
    ).update(status='completed')
    return f"Marked {count} appointments as completed"


@shared_task
def mark_no_show_appointments():
    """Mark appointments as no_show if 30+ minutes past start time and still scheduled."""
    cutoff = timezone.now() - timedelta(minutes=30)
    from .models import Appointment
    count = Appointment.objects.filter(
        status='scheduled',
        booking_status='confirmed',
        slot__start_datetime__lt=cutoff,
        slot__end_datetime__gt=timezone.now() - timedelta(hours=24)
    ).update(status='no_show')
    return f"Marked {count} appointments as no_show"
