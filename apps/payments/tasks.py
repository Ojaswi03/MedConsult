"""
Celery tasks for payment processing.
"""
from celery import shared_task
from django.utils import timezone
from datetime import timedelta


@shared_task
def expire_held_appointments():
    """
    Cancel appointments that have been held for more than 15 minutes without payment.
    Frees the slot so other patients can book.
    """
    from django.db import transaction
    from apps.scheduling.models import Appointment, Slot

    cutoff = timezone.now() - timedelta(minutes=15)
    held = list(
        Appointment.objects.filter(
            booking_status='held',
            created_at__lt=cutoff
        ).select_related('slot')
    )

    count = 0
    for appointment in held:
        with transaction.atomic():
            slot = Slot.objects.select_for_update().get(pk=appointment.slot_id)
            appointment.booking_status = 'expired'
            appointment.status = 'cancelled'
            appointment.save(update_fields=['booking_status', 'status'])
            slot.is_booked = False
            if slot.current_bookings > 0:
                slot.current_bookings -= 1
            slot.save()
            count += 1

    return f"Expired {count} held appointments"
