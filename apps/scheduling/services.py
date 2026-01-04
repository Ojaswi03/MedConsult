"""
Services for scheduling app - handles slot generation and booking logic.
"""
from datetime import datetime, timedelta, time
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from .models import AvailabilityWindow, AvailabilityWindowTypeConfig, Slot, Appointment, SlotChangeLog, AppointmentTypeConfig
from .consumers import sync_broadcast_to_doctor_calendar, sync_broadcast_to_patient_slots


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
    days_ahead=30,
    type_configs=None
):
    """
    Create a new availability window for a doctor.
    Optionally generates slots immediately.

    type_configs: list of (appointment_type, is_enabled, price) tuples for multi-type support
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

    # Save type configs if provided (for multi-type support)
    if type_configs:
        for type_code, is_enabled, price in type_configs:
            AvailabilityWindowTypeConfig.objects.create(
                window=window,
                appointment_type=type_code,
                is_enabled=is_enabled,
                price=price if price else Decimal('0')
            )

    if auto_generate_slots:
        generate_slots_for_window_v2(
            window,
            timezone.now().date(),
            timezone.now().date() + timedelta(days=days_ahead)
        )

    return window


@transaction.atomic
def update_availability_window(window_id, doctor_profile, type_configs=None, regenerate_slots=False, **kwargs):
    """
    Update an existing availability window.

    Args:
        window_id: The window ID to update
        doctor_profile: The doctor profile
        type_configs: Optional list of (appointment_type, is_enabled, price) tuples
        regenerate_slots: If True, delete future unbooked slots and regenerate
        **kwargs: Fields to update on the window
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

    # Update window fields
    for key, value in kwargs.items():
        if hasattr(window, key):
            setattr(window, key, value)
    window.save()

    # Update type configs if provided
    if type_configs is not None:
        # Delete existing type configs
        window.type_configs.all().delete()

        # Create new type configs
        for type_code, is_enabled, price in type_configs:
            AvailabilityWindowTypeConfig.objects.create(
                window=window,
                appointment_type=type_code,
                is_enabled=is_enabled,
                price=price if price else Decimal('0')
            )

    # Regenerate slots if requested
    if regenerate_slots:
        # Delete future unbooked slots
        from django.utils import timezone
        future_slots = Slot.objects.filter(
            availability_window=window,
            start_datetime__gt=timezone.now(),
            is_booked=False
        )
        future_slots.delete()

        # Generate new slots
        generate_slots_for_window_v2(
            window,
            timezone.now().date(),
            timezone.now().date() + timedelta(days=30)
        )

    # Broadcast WebSocket updates
    sync_broadcast_to_doctor_calendar(doctor_profile.id, 'window_updated', {
        'window_id': window_id,
        'data': {
            'weekday': window.weekday,
            'start_time': str(window.start_time),
            'end_time': str(window.end_time)
        }
    })

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
    deleted_slot_ids = []
    if cancel_future_slots:
        # Delete future unbooked slots from this window
        future_slots = Slot.objects.filter(
            availability_window=window,
            start_datetime__gt=timezone.now(),
            is_booked=False
        )
        deleted_count = future_slots.count()
        deleted_slot_ids = list(future_slots.values_list('id', flat=True))

        # Log deletions for real-time updates
        for slot in future_slots:
            log_slot_change(doctor_profile, slot, 'deleted')

        future_slots.delete()

    # Soft delete - mark as inactive
    window.is_active = False
    window.save()

    # Broadcast WebSocket updates
    sync_broadcast_to_doctor_calendar(doctor_profile.id, 'window_deleted', {
        'window_id': window_id,
        'data': {
            'deleted_slots': deleted_slot_ids
        }
    })
    # Notify patients about removed slots
    for slot_id in deleted_slot_ids:
        sync_broadcast_to_patient_slots(doctor_profile.id, 'slot_taken', {
            'slot_id': slot_id
        })

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

    # Broadcast WebSocket updates
    sync_broadcast_to_doctor_calendar(doctor_profile.id, 'slot_blocked', {
        'slot_id': slot.id,
        'data': {
            'start_datetime': slot.start_datetime.isoformat(),
            'reason': reason
        }
    })
    sync_broadcast_to_patient_slots(doctor_profile.id, 'slot_taken', {
        'slot_id': slot.id
    })

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

    # Broadcast WebSocket updates
    sync_broadcast_to_doctor_calendar(doctor_profile.id, 'slot_unblocked', {
        'slot_id': slot.id,
        'data': {
            'start_datetime': slot.start_datetime.isoformat()
        }
    })
    sync_broadcast_to_patient_slots(doctor_profile.id, 'slot_available', {
        'slot_id': slot.id,
        'data': {
            'start_datetime': slot.start_datetime.isoformat(),
            'appointment_type': slot.appointment_type
        }
    })

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

    slot_id_copy = slot.id
    log_slot_change(doctor_profile, slot, 'deleted')
    slot.delete()

    # Broadcast WebSocket updates
    sync_broadcast_to_doctor_calendar(doctor_profile.id, 'slot_deleted', {
        'slot_id': slot_id_copy
    })
    sync_broadcast_to_patient_slots(doctor_profile.id, 'slot_taken', {
        'slot_id': slot_id_copy
    })

    return True


# ============ ENHANCED SLOT GENERATION ============

def generate_slots_for_window_v2(availability_window, start_date, end_date):
    """
    Generate slots with buffer times and appointment types.
    Enhanced version that supports multi-type appointments.
    Creates separate slots for each enabled appointment type in the window.
    """
    created_slots = []
    current_date = start_date

    # Get enabled type configs for this window
    type_configs = list(availability_window.type_configs.filter(is_enabled=True))

    # If no type configs exist (legacy), use the window's default appointment_type
    if not type_configs:
        type_configs = [{'appointment_type': availability_window.appointment_type, 'price': Decimal('0')}]
    else:
        type_configs = [{'appointment_type': tc.appointment_type, 'price': tc.price} for tc in type_configs]

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
                # Create a slot for each enabled appointment type
                for type_config in type_configs:
                    apt_type = type_config['appointment_type']

                    # Check if slot already exists for this time and type
                    existing_slot = Slot.objects.filter(
                        doctor=availability_window.doctor,
                        start_datetime=current_slot_start,
                        appointment_type=apt_type
                    ).first()

                    if not existing_slot:
                        slot = Slot.objects.create(
                            doctor=availability_window.doctor,
                            availability_window=availability_window,
                            start_datetime=current_slot_start,
                            end_datetime=current_slot_start + slot_duration,
                            appointment_type=apt_type
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

    # Broadcast WebSocket updates
    sync_broadcast_to_doctor_calendar(slot.doctor.id, 'slot_booked', {
        'slot_id': slot.id,
        'data': {
            'patient_name': patient.user.get_full_name(),
            'start_datetime': slot.start_datetime.isoformat()
        }
    })
    sync_broadcast_to_patient_slots(slot.doctor.id, 'slot_taken', {
        'slot_id': slot.id
    })

    return appointment


@transaction.atomic
def cancel_appointment(appointment):
    """
    Cancel an appointment and free up the slot.
    """
    if not appointment.can_cancel():
        raise ValueError('This appointment cannot be cancelled.')

    slot = appointment.slot
    doctor_id = slot.doctor.id

    # Free up the slot
    slot.is_booked = False
    slot.save()

    # Update appointment status
    appointment.status = 'cancelled'
    appointment.save()

    # Broadcast WebSocket updates
    sync_broadcast_to_doctor_calendar(doctor_id, 'slot_unblocked', {
        'slot_id': slot.id,
        'data': {
            'start_datetime': slot.start_datetime.isoformat(),
            'reason': 'appointment_cancelled'
        }
    })
    sync_broadcast_to_patient_slots(doctor_id, 'slot_available', {
        'slot_id': slot.id,
        'data': {
            'start_datetime': slot.start_datetime.isoformat(),
            'appointment_type': slot.appointment_type
        }
    })

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
    doctor_id = old_slot.doctor.id
    old_slot.is_booked = False
    old_slot.save()

    # Book new slot
    new_slot.is_booked = True
    new_slot.save()

    # Update appointment
    appointment.slot = new_slot
    appointment.save()

    # Broadcast WebSocket updates - old slot is now available
    sync_broadcast_to_patient_slots(doctor_id, 'slot_available', {
        'slot_id': old_slot.id,
        'data': {
            'start_datetime': old_slot.start_datetime.isoformat(),
            'appointment_type': old_slot.appointment_type
        }
    })
    # New slot is now taken
    sync_broadcast_to_patient_slots(doctor_id, 'slot_taken', {
        'slot_id': new_slot.id
    })

    return appointment
