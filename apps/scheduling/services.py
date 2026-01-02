"""
Services for scheduling app - handles slot generation and booking logic.
"""
from datetime import datetime, timedelta, time
from django.db import transaction
from django.utils import timezone
from .models import AvailabilityWindow, Slot, Appointment, SlotChangeLog, AppointmentTypeConfig


# ============ SLOT CHANGE LOGGING ============

def log_slot_change(doctor_profile, slot, change_type):
    """
    Log slot changes for real-time notifications to patients.
    """
    SlotChangeLog.objects.create(
        doctor=doctor_profile,
        slot=slot if change_type != 'deleted' else None,
        change_type=change_type
    )


# ============ AVAILABILITY WINDOW SERVICES ============

def check_window_overlap(doctor_profile, weekday, start_time, end_time, exclude_id=None):
    """
    Check if a time window overlaps with existing windows.
    Returns True if there's an overlap.
    """
    query = AvailabilityWindow.objects.filter(
        doctor=doctor_profile,
        weekday=weekday,
        is_active=True
    )

    if exclude_id:
        query = query.exclude(id=exclude_id)

    for window in query:
        # Check for time overlap
        if start_time < window.end_time and end_time > window.start_time:
            return True
    return False


@transaction.atomic
def create_availability_window(
    doctor_profile,
    weekday,
    start_time,
    end_time,
    slot_duration_minutes=30,
    buffer_before_minutes=0,
    buffer_after_minutes=0,
    appointment_type='video',
    is_recurring=True,
    effective_date=None,
    end_date=None,
    auto_generate_slots=True,
    days_ahead=30
):
    """
    Create a new availability window for a doctor.
    Optionally generates slots immediately.
    """
    # Validate no overlap with existing windows
    if check_window_overlap(doctor_profile, weekday, start_time, end_time):
        raise ValueError('This time window overlaps with an existing availability window.')

    window = AvailabilityWindow.objects.create(
        doctor=doctor_profile,
        weekday=weekday,
        start_time=start_time,
        end_time=end_time,
        slot_duration_minutes=slot_duration_minutes,
        buffer_before_minutes=buffer_before_minutes,
        buffer_after_minutes=buffer_after_minutes,
        appointment_type=appointment_type,
        is_recurring=is_recurring,
        effective_date=effective_date,
        end_date=end_date,
        is_active=True
    )

    if auto_generate_slots:
        generate_slots_for_window_v2(
            window,
            timezone.now().date(),
            timezone.now().date() + timedelta(days=days_ahead)
        )

    return window


@transaction.atomic
def update_availability_window(window_id, doctor_profile, **kwargs):
    """
    Update an existing availability window.
    """
    try:
        window = AvailabilityWindow.objects.get(id=window_id, doctor=doctor_profile)
    except AvailabilityWindow.DoesNotExist:
        raise ValueError('Availability window not found.')

    # Check for time conflicts if changing times
    if 'start_time' in kwargs or 'end_time' in kwargs or 'weekday' in kwargs:
        overlapping = check_window_overlap(
            doctor_profile,
            kwargs.get('weekday', window.weekday),
            kwargs.get('start_time', window.start_time),
            kwargs.get('end_time', window.end_time),
            exclude_id=window_id
        )
        if overlapping:
            raise ValueError('This time window overlaps with an existing availability window.')

    for key, value in kwargs.items():
        if hasattr(window, key):
            setattr(window, key, value)
    window.save()

    return window


@transaction.atomic
def delete_availability_window(window_id, doctor_profile, cancel_future_slots=True):
    """
    Delete (deactivate) an availability window and optionally cancel future unbooked slots.
    """
    try:
        window = AvailabilityWindow.objects.get(id=window_id, doctor=doctor_profile)
    except AvailabilityWindow.DoesNotExist:
        raise ValueError('Availability window not found.')

    deleted_count = 0
    if cancel_future_slots:
        # Delete future unbooked slots from this window
        future_slots = Slot.objects.filter(
            availability_window=window,
            start_datetime__gt=timezone.now(),
            is_booked=False
        )
        deleted_count = future_slots.count()

        # Log deletions for real-time updates
        for slot in future_slots:
            log_slot_change(doctor_profile, slot, 'deleted')

        future_slots.delete()

    # Soft delete - mark as inactive
    window.is_active = False
    window.save()

    return {'deleted_slots': deleted_count}


# ============ MANUAL SLOT SERVICES ============

@transaction.atomic
def create_manual_slot(
    doctor_profile,
    start_datetime,
    end_datetime,
    appointment_type='video',
    is_urgent=False,
    max_capacity=1,
    notes=''
):
    """
    Create a manual slot (for urgent appointments or overrides).
    """
    # Check for conflicts
    existing = Slot.objects.filter(
        doctor=doctor_profile,
        start_datetime__lt=end_datetime,
        end_datetime__gt=start_datetime
    ).exists()

    if existing:
        raise ValueError('A slot already exists at this time.')

    slot = Slot.objects.create(
        doctor=doctor_profile,
        start_datetime=start_datetime,
        end_datetime=end_datetime,
        appointment_type=appointment_type,
        is_urgent=is_urgent,
        max_capacity=max_capacity,
        notes=notes
    )

    # Log change for real-time updates
    log_slot_change(doctor_profile, slot, 'created')

    return slot


@transaction.atomic
def block_slot(slot_id, doctor_profile, reason=''):
    """
    Block a slot (mark as unavailable).
    """
    try:
        slot = Slot.objects.get(id=slot_id, doctor=doctor_profile)
    except Slot.DoesNotExist:
        raise ValueError('Slot not found.')

    if slot.is_booked:
        raise ValueError('Cannot block a slot that is already booked.')

    slot.is_blocked = True
    slot.notes = reason
    slot.save()

    log_slot_change(doctor_profile, slot, 'updated')

    return slot


@transaction.atomic
def unblock_slot(slot_id, doctor_profile):
    """
    Unblock a slot (make available again).
    """
    try:
        slot = Slot.objects.get(id=slot_id, doctor=doctor_profile)
    except Slot.DoesNotExist:
        raise ValueError('Slot not found.')

    slot.is_blocked = False
    slot.save()

    log_slot_change(doctor_profile, slot, 'updated')

    return slot


@transaction.atomic
def delete_slot(slot_id, doctor_profile):
    """
    Delete an unbooked slot.
    """
    try:
        slot = Slot.objects.get(id=slot_id, doctor=doctor_profile)
    except Slot.DoesNotExist:
        raise ValueError('Slot not found.')

    if slot.is_booked:
        raise ValueError('Cannot delete a booked slot. Cancel the appointment first.')

    log_slot_change(doctor_profile, slot, 'deleted')
    slot.delete()

    return True


# ============ ENHANCED SLOT GENERATION ============

def generate_slots_for_window_v2(availability_window, start_date, end_date):
    """
    Generate slots with buffer times and appointment types.
    Enhanced version that respects all new fields.
    """
    created_slots = []
    current_date = start_date

    while current_date <= end_date:
        # Check if current_date matches the availability window's weekday
        if current_date.weekday() == availability_window.weekday:
            # Check effective dates for non-recurring
            if not availability_window.is_recurring:
                if availability_window.effective_date and current_date != availability_window.effective_date:
                    current_date += timedelta(days=1)
                    continue
            elif availability_window.end_date and current_date > availability_window.end_date:
                break

            # Check effective start date
            if availability_window.effective_date and current_date < availability_window.effective_date:
                current_date += timedelta(days=1)
                continue

            start_datetime = timezone.make_aware(
                datetime.combine(current_date, availability_window.start_time)
            )
            end_datetime = timezone.make_aware(
                datetime.combine(current_date, availability_window.end_time)
            )

            # Calculate total time per slot including buffers
            slot_duration = timedelta(minutes=availability_window.slot_duration_minutes)
            buffer_before = timedelta(minutes=availability_window.buffer_before_minutes)
            buffer_after = timedelta(minutes=availability_window.buffer_after_minutes)
            total_slot_time = slot_duration + buffer_before + buffer_after

            # Start after buffer_before
            current_slot_start = start_datetime + buffer_before

            while current_slot_start + slot_duration <= end_datetime - buffer_after:
                # Check if slot already exists
                existing_slot = Slot.objects.filter(
                    doctor=availability_window.doctor,
                    start_datetime=current_slot_start
                ).first()

                if not existing_slot:
                    slot = Slot.objects.create(
                        doctor=availability_window.doctor,
                        availability_window=availability_window,
                        start_datetime=current_slot_start,
                        end_datetime=current_slot_start + slot_duration,
                        appointment_type=availability_window.appointment_type
                    )
                    created_slots.append(slot)
                    log_slot_change(availability_window.doctor, slot, 'created')

                current_slot_start += total_slot_time

        current_date += timedelta(days=1)

    return created_slots


def generate_slots_for_window(availability_window, start_date, end_date):
    """
    Generate slots for a specific availability window between start_date and end_date.
    Returns list of created Slot objects.
    """
    created_slots = []
    current_date = start_date

    while current_date <= end_date:
        # Check if current_date matches the availability window's weekday
        if current_date.weekday() == availability_window.weekday:
            # Generate slots for this day
            start_datetime = timezone.make_aware(
                datetime.combine(current_date, availability_window.start_time)
            )
            end_datetime = timezone.make_aware(
                datetime.combine(current_date, availability_window.end_time)
            )

            current_slot_start = start_datetime
            slot_duration = timedelta(minutes=availability_window.slot_duration_minutes)

            while current_slot_start + slot_duration <= end_datetime:
                # Check if slot already exists
                existing_slot = Slot.objects.filter(
                    doctor=availability_window.doctor,
                    start_datetime=current_slot_start
                ).first()

                if not existing_slot:
                    slot = Slot.objects.create(
                        doctor=availability_window.doctor,
                        availability_window=availability_window,
                        start_datetime=current_slot_start,
                        end_datetime=current_slot_start + slot_duration
                    )
                    created_slots.append(slot)

                current_slot_start += slot_duration

        current_date += timedelta(days=1)

    return created_slots


def generate_slots_for_doctor(doctor_profile, days_ahead=30):
    """
    Generate slots for all availability windows of a doctor for the next N days.
    """
    start_date = timezone.now().date()
    end_date = start_date + timedelta(days=days_ahead)

    all_created_slots = []
    for window in doctor_profile.availability_windows.filter(is_active=True):
        slots = generate_slots_for_window(window, start_date, end_date)
        all_created_slots.extend(slots)

    return all_created_slots


@transaction.atomic
def book_appointment(slot, patient, reason=''):
    """
    Book an appointment for a patient in a specific slot.
    Returns the created Appointment object or raises an exception.
    """
    if slot.is_booked:
        raise ValueError('This slot is already booked.')

    if slot.start_datetime <= timezone.now():
        raise ValueError('Cannot book a slot in the past.')

    # Mark slot as booked
    slot.is_booked = True
    slot.save()

    # Create appointment
    appointment = Appointment.objects.create(
        slot=slot,
        patient=patient,
        doctor=slot.doctor,
        reason=reason,
        status='scheduled'
    )

    return appointment


@transaction.atomic
def cancel_appointment(appointment):
    """
    Cancel an appointment and free up the slot.
    """
    if not appointment.can_cancel():
        raise ValueError('This appointment cannot be cancelled.')

    # Free up the slot
    appointment.slot.is_booked = False
    appointment.slot.save()

    # Update appointment status
    appointment.status = 'cancelled'
    appointment.save()

    return appointment


@transaction.atomic
def reschedule_appointment(appointment, new_slot):
    """
    Reschedule an appointment to a new slot.
    """
    if not appointment.can_cancel():
        raise ValueError('This appointment cannot be rescheduled.')

    if new_slot.is_booked:
        raise ValueError('The new slot is already booked.')

    if new_slot.start_datetime <= timezone.now():
        raise ValueError('Cannot reschedule to a slot in the past.')

    # Free up old slot
    old_slot = appointment.slot
    old_slot.is_booked = False
    old_slot.save()

    # Book new slot
    new_slot.is_booked = True
    new_slot.save()

    # Update appointment
    appointment.slot = new_slot
    appointment.save()

    return appointment
