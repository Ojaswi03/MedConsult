"""
Services for scheduling app - handles slot generation and booking logic.
"""
from datetime import datetime, timedelta, time
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from .models import AvailabilityWindow, AvailabilityWindowTypeConfig, Slot, Appointment, SlotChangeLog, AppointmentTypeConfig, HealthRecord
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

    # Notify waitlisted patients
    from .tasks import notify_waitlist_for_doctor
    notify_waitlist_for_doctor.delay(doctor_profile.id)

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
        # Check for full-day availability exceptions
        from .models import AvailabilityException
        exception = AvailabilityException.objects.filter(
            doctor=availability_window.doctor,
            date=current_date
        ).first()
        if exception and not exception.start_time:
            # Full-day block — skip slot generation entirely for this date
            current_date += timedelta(days=1)
            continue

        # Check if current_date matches the availability window's weekday
        if current_date.weekday() == availability_window.weekday:
            # Check effective dates for non-recurring
            if not availability_window.is_recurring:
                if availability_window.effective_date:
                    if current_date != availability_window.effective_date:
                        current_date += timedelta(days=1)
                        continue
                else:
                    # No specific date set — generate only the first matching weekday, then stop
                    pass  # slots will be created below, then we break after
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

            # Non-recurring: stop after the first matching day is processed
            if not availability_window.is_recurring:
                break

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
        slots = generate_slots_for_window_v2(window, start_date, end_date)
        all_created_slots.extend(slots)

    return all_created_slots


@transaction.atomic
def book_appointment(slot, patient, reason=''):
    """
    Book an appointment for a patient in a specific slot.
    Returns the created Appointment object or raises an exception.
    Supports group sessions (max_capacity > 1).
    """
    slot = Slot.objects.select_for_update().get(pk=slot.pk)

    if slot.start_datetime <= timezone.now():
        raise ValueError('Cannot book a slot in the past.')

    if slot.is_blocked:
        raise ValueError('This slot is not available.')

    # Handle group vs single slot
    if slot.max_capacity > 1:
        if slot.appointments.filter(patient=patient, status='scheduled').exists():
            raise ValueError('You have already booked this group session.')
        if slot.current_bookings >= slot.max_capacity:
            raise ValueError('This slot is fully booked.')
        slot.current_bookings += 1
        if slot.current_bookings >= slot.max_capacity:
            slot.is_booked = True
        slot.save()
    else:
        if slot.is_booked:
            raise ValueError('This slot is already booked.')
        slot.is_booked = True
        slot.save()

    # Create appointment as held — caller confirms after payment or immediately for free slots
    appointment = Appointment.objects.create(
        slot=slot,
        patient=patient,
        doctor=slot.doctor,
        reason=reason,
        status='scheduled',
        booking_status='held',
    )

    # In-app notifications fire immediately regardless of payment status
    from apps.accounts.services import create_notification
    create_notification(
        patient, 'appointment_booked',
        f"Appointment booked with Dr. {slot.doctor.user.get_display_name()}",
        f"Your appointment is on {slot.start_datetime.strftime('%B %d, %Y at %I:%M %p')}.",
        link=f"/patient/appointments/"
    )
    create_notification(
        slot.doctor.user, 'appointment_booked',
        f"New appointment: {patient.get_display_name()}",
        f"{patient.get_display_name()} booked a slot on {slot.start_datetime.strftime('%B %d, %Y at %I:%M %p')}.",
        link=f"/doctor/schedule/"
    )

    # Broadcast WebSocket updates
    sync_broadcast_to_doctor_calendar(slot.doctor.id, 'slot_booked', {
        'slot_id': slot.id,
        'data': {
            'patient_name': patient.get_full_name(),
            'start_datetime': slot.start_datetime.isoformat()
        }
    })
    sync_broadcast_to_patient_slots(slot.doctor.id, 'slot_taken', {
        'slot_id': slot.id
    })

    return appointment


def confirm_free_appointment(appointment):
    """
    Confirm a free (no-charge) appointment immediately after booking.
    Sends confirmation email/SMS. Only call for slots where get_price() == 0.
    """
    appointment.booking_status = 'confirmed'
    appointment.save(update_fields=['booking_status'])

    from .tasks import send_appointment_confirmation_email, send_sms_appointment_confirmation
    send_appointment_confirmation_email.delay(appointment.id)
    if appointment.patient.phone_notifications and appointment.patient.phone:
        send_sms_appointment_confirmation.delay(appointment.id)


@transaction.atomic
def cancel_appointment(appointment):
    """
    Cancel an appointment and free up the slot.
    """
    if not appointment.can_cancel():
        raise ValueError('This appointment cannot be cancelled.')

    slot = appointment.slot
    doctor_id = slot.doctor.id
    patient = appointment.patient
    doctor = appointment.doctor

    # Free up the slot
    slot.is_booked = False
    if slot.current_bookings > 0:
        slot.current_bookings -= 1
    slot.save()

    # Update appointment status
    appointment.status = 'cancelled'
    appointment.save()

    # In-app notifications
    from apps.accounts.services import create_notification
    create_notification(
        patient, 'appointment_cancelled',
        "Appointment cancelled",
        f"Your appointment with Dr. {doctor.user.get_display_name()} on {slot.start_datetime.strftime('%B %d, %Y')} has been cancelled.",
        link="/patient/appointments/"
    )
    create_notification(
        doctor.user, 'appointment_cancelled',
        f"Appointment cancelled by {patient.get_display_name()}",
        f"{patient.get_display_name()} cancelled their appointment on {slot.start_datetime.strftime('%B %d, %Y at %I:%M %p')}.",
        link="/doctor/schedule/"
    )

    # Notify waitlisted patients
    from .tasks import notify_waitlist_for_doctor
    notify_waitlist_for_doctor.delay(doctor_id)

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
    Old slot is freed; new slot is booked.
    """
    if appointment.status != 'scheduled':
        raise ValueError('Only scheduled appointments can be rescheduled.')

    if appointment.start_datetime <= timezone.now():
        raise ValueError('Cannot reschedule a past appointment.')

    if new_slot.is_booked or new_slot.is_blocked:
        raise ValueError('The selected slot is not available.')

    if new_slot.start_datetime <= timezone.now():
        raise ValueError('Cannot reschedule to a slot in the past.')

    old_slot = appointment.slot
    doctor_id = old_slot.doctor.id

    # Free the old slot
    old_slot.is_booked = False
    old_slot.save()

    # Book the new slot
    new_slot.is_booked = True
    new_slot.save()

    appointment.slot = new_slot
    appointment.save()

    log_slot_change(old_slot.doctor, old_slot, 'updated')
    log_slot_change(new_slot.doctor, new_slot, 'booked')

    sync_broadcast_to_patient_slots(doctor_id, 'slot_available', {'slot_id': old_slot.id})
    sync_broadcast_to_patient_slots(doctor_id, 'slot_taken', {'slot_id': new_slot.id})

    return appointment


# ============ REVIEW SERVICES ============

@transaction.atomic
def create_prescription(appointment, diagnosis, medications, instructions='', notes=''):
    """Create a prescription for a completed appointment."""
    from .models import Prescription

    if appointment.status != 'completed':
        raise ValueError('Prescriptions can only be written for completed appointments.')

    if Prescription.objects.filter(appointment=appointment).exists():
        raise ValueError('A prescription has already been written for this appointment.')

    prescription = Prescription.objects.create(
        appointment=appointment,
        doctor=appointment.doctor,
        patient=appointment.patient,
        diagnosis=diagnosis,
        medications=medications,
        instructions=instructions,
        notes=notes,
    )

    # Notify patient
    from apps.accounts.services import create_notification
    create_notification(
        appointment.patient, 'prescription_ready',
        f"Prescription ready from Dr. {appointment.doctor.user.get_display_name()}",
        "Your prescription is now available. You can download it from your appointments.",
        link=f"/patient/appointments/{appointment.id}/prescription/download/"
    )

    return prescription


@transaction.atomic
def create_review(appointment, patient, rating, comment=''):
    """
    Create a review for a completed appointment.

    Args:
        appointment: The Appointment object being reviewed
        patient: The User who is leaving the review
        rating: Integer 1-5
        comment: Optional text comment

    Returns:
        Review object

    Raises:
        ValueError: If review cannot be created
    """
    from .models import Review

    # Validate patient is the one who had the appointment
    if appointment.patient != patient:
        raise ValueError('You can only review your own appointments.')

    # Validate appointment is completed
    if appointment.status != 'completed':
        raise ValueError('You can only review completed appointments.')

    # Check for existing review
    if Review.objects.filter(appointment=appointment).exists():
        raise ValueError('You have already reviewed this appointment.')

    # Validate rating
    if not 1 <= rating <= 5:
        raise ValueError('Rating must be between 1 and 5.')

    review = Review.objects.create(
        appointment=appointment,
        patient=patient,
        doctor=appointment.doctor,
        rating=rating,
        comment=comment
    )

    return review


@transaction.atomic
def update_review(review, patient, rating=None, comment=None):
    """
    Update an existing review.

    Args:
        review: The Review object to update
        patient: The User updating the review
        rating: New rating (1-5) or None to keep current
        comment: New comment or None to keep current

    Returns:
        Updated Review object
    """
    if review.patient != patient:
        raise ValueError('You can only update your own reviews.')

    if rating is not None:
        if not 1 <= rating <= 5:
            raise ValueError('Rating must be between 1 and 5.')
        review.rating = rating

    if comment is not None:
        review.comment = comment

    review.save()
    return review


@transaction.atomic
def delete_review(review, patient):
    """
    Delete a review.

    Args:
        review: The Review object to delete
        patient: The User deleting the review

    Returns:
        True if deleted successfully
    """
    if review.patient != patient:
        raise ValueError('You can only delete your own reviews.')

    review.delete()
    return True


# ============ TIME-OFF SERVICES ============

@transaction.atomic
def create_time_off_block(doctor_profile, start_date, end_date, reason=''):
    """Create a time-off block and block all existing unbooked slots in that range."""
    from .models import TimeOffBlock, Slot
    block = TimeOffBlock.objects.create(
        doctor=doctor_profile, start_date=start_date, end_date=end_date, reason=reason
    )
    Slot.objects.filter(
        doctor=doctor_profile,
        start_datetime__date__gte=start_date,
        start_datetime__date__lte=end_date,
        is_booked=False
    ).update(is_blocked=True, notes=f'Time off: {reason}' if reason else 'Time off')
    return block


@transaction.atomic
def delete_time_off_block(block_id, doctor_profile):
    """Delete a time-off block and unblock slots that were blocked by it."""
    from .models import TimeOffBlock, Slot
    block = TimeOffBlock.objects.get(id=block_id, doctor=doctor_profile)
    Slot.objects.filter(
        doctor=doctor_profile,
        start_datetime__date__gte=block.start_date,
        start_datetime__date__lte=block.end_date,
        is_blocked=True,
        is_booked=False,
        notes__startswith='Time off'
    ).update(is_blocked=False, notes='')
    block.delete()


# ============ WAITLIST SERVICES ============

@transaction.atomic
def join_waitlist(doctor_profile, patient, appointment_type='', preferred_date=None, notes=''):
    """Add a patient to the waitlist for a doctor."""
    from .models import WaitlistEntry
    entry, created = WaitlistEntry.objects.get_or_create(
        doctor=doctor_profile, patient=patient,
        defaults={
            'appointment_type': appointment_type,
            'preferred_date': preferred_date,
            'notes': notes
        }
    )
    if created:
        from apps.accounts.services import create_notification
        create_notification(
            patient, 'waitlist_slot_available',
            f"Added to waitlist for Dr. {doctor_profile.user.get_display_name()}",
            "You'll be notified when a slot opens up.",
            link=f"/patient/doctors/{doctor_profile.id}/"
        )
    return entry, created


@transaction.atomic
def leave_waitlist(doctor_profile, patient):
    """Remove a patient from the waitlist."""
    from .models import WaitlistEntry
    WaitlistEntry.objects.filter(doctor=doctor_profile, patient=patient).delete()


# ============ HEALTH RECORD SERVICES ============

@transaction.atomic
def create_health_record(patient, record_type, title, description='', file=None, date_of_record=None):
    """Create a health record for a patient."""
    return HealthRecord.objects.create(
        patient=patient,
        record_type=record_type,
        title=title,
        description=description,
        file=file,
        date_of_record=date_of_record
    )


@transaction.atomic
def share_health_record_with_doctor(record, doctor_profile):
    """Share a health record with a doctor and notify them."""
    record.shared_with_doctors.add(doctor_profile)
    from apps.accounts.services import create_notification
    create_notification(
        doctor_profile.user, 'health_record_shared',
        f"{record.patient.get_display_name()} shared a health record",
        f"'{record.title}' has been shared with you.",
        link=f"/patient/health-records/{record.id}/"
    )


def get_patient_health_records(patient):
    """Get all health records for a patient."""
    return HealthRecord.objects.filter(patient=patient)


def get_shared_records_for_doctor(doctor_profile, patient):
    """Get health records shared with a specific doctor by a patient."""
    return HealthRecord.objects.filter(patient=patient, shared_with_doctors=doctor_profile)


# ============ REFERRAL SERVICES ============

@transaction.atomic
def create_referral(referring_doctor, referred_to_doctor, patient, reason, notes=''):
    """Create a referral from one doctor to another for a patient."""
    from .models import Referral
    from datetime import timedelta
    from apps.accounts.services import create_notification
    referral = Referral.objects.create(
        referring_doctor=referring_doctor,
        referred_to_doctor=referred_to_doctor,
        patient=patient,
        reason=reason,
        notes=notes,
        expires_at=timezone.now() + timedelta(days=30)
    )
    create_notification(
        patient, 'referral_received',
        f"Dr. {referring_doctor.user.get_display_name()} referred you to Dr. {referred_to_doctor.user.get_display_name()}",
        reason,
        link=f"/patient/doctors/{referred_to_doctor.id}/"
    )
    return referral


# ============ AVAILABILITY EXCEPTION SERVICES ============

@transaction.atomic
def create_availability_exception(doctor_profile, date, start_time=None, end_time=None, reason=''):
    """Create a one-off availability exception for a doctor on a specific date."""
    from .models import AvailabilityException
    exception, created = AvailabilityException.objects.update_or_create(
        doctor=doctor_profile, date=date,
        defaults={'start_time': start_time, 'end_time': end_time, 'reason': reason}
    )
    # Block existing unbooked slots on that date that fall outside the exception window
    _apply_exception_to_slots(doctor_profile, exception)
    return exception, created


def _apply_exception_to_slots(doctor_profile, exception):
    """Block slots on the exception date outside the allowed time window."""
    qs = Slot.objects.filter(
        doctor=doctor_profile,
        start_datetime__date=exception.date,
        is_booked=False
    )
    if exception.start_time and exception.end_time:
        # Block slots that are OUTSIDE the exception window
        qs = qs.exclude(
            start_datetime__time__gte=exception.start_time,
            end_datetime__time__lte=exception.end_time
        )
    # Block everything (full-day block) or the filtered slots
    qs.update(is_blocked=True, notes='Exception block')


@transaction.atomic
def delete_availability_exception(exception_id, doctor_profile):
    """Delete an availability exception and unblock slots that were blocked by it."""
    from .models import AvailabilityException
    exc = AvailabilityException.objects.get(id=exception_id, doctor=doctor_profile)
    exc_date = exc.date
    exc.delete()
    # Unblock slots that were blocked by this exception (only if no time-off covers them)
    from .models import TimeOffBlock
    time_off_active = TimeOffBlock.objects.filter(
        doctor=doctor_profile,
        start_date__lte=exc_date,
        end_date__gte=exc_date
    ).exists()
    if not time_off_active:
        Slot.objects.filter(
            doctor=doctor_profile,
            start_datetime__date=exc_date,
            is_blocked=True,
            is_booked=False,
            notes='Exception block'
        ).update(is_blocked=False, notes='')


# ============ BILLING SERVICES ============

def generate_billing_pdf(appointment, billing_ctx):
    """Generate an itemized billing summary PDF. Returns BytesIO buffer."""
    from io import BytesIO
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
    from reportlab.lib import colors
    from reportlab.lib.units import inch
    from reportlab.lib.enums import TA_RIGHT

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=36)
    styles = getSampleStyleSheet()
    right_style = ParagraphStyle('Right', parent=styles['Normal'], alignment=TA_RIGHT)
    story = []

    # ── Header ────────────────────────────────────────────────────────────────
    story.append(Paragraph("BILLING SUMMARY", styles['Title']))
    story.append(Paragraph("MedConsult Telehealth Platform", styles['Normal']))
    story.append(Paragraph(f"Invoice #{appointment.id:06d}", styles['Normal']))
    story.append(Spacer(1, 0.25 * inch))

    # ── Patient Info ──────────────────────────────────────────────────────────
    story.append(Paragraph("<b>Patient Information</b>", styles['Heading2']))
    patient_profile = billing_ctx.get('patient_profile')
    patient_data = [
        ["Patient Name:", appointment.patient.get_display_name()],
        ["Email:", appointment.patient.email],
    ]
    if patient_profile:
        if patient_profile.date_of_birth:
            patient_data.append(["Date of Birth:", str(patient_profile.date_of_birth)])
        if billing_ctx.get('has_insurance'):
            patient_data.append(["Insurance Provider:", billing_ctx['insurance_provider']])
            patient_data.append(["Policy Number:", billing_ctx['insurance_policy_number']])

    pt_table = Table(patient_data, colWidths=[2 * inch, 4 * inch])
    pt_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(pt_table)
    story.append(Spacer(1, 0.2 * inch))

    # ── Provider Info ─────────────────────────────────────────────────────────
    story.append(Paragraph("<b>Provider Information</b>", styles['Heading2']))
    doc_data = [
        ["Provider Name:", f"Dr. {appointment.doctor.user.get_display_name()}"],
        ["Specialization:", appointment.doctor.specialization],
    ]
    if appointment.doctor.npi_number:
        doc_data.append(["NPI Number:", appointment.doctor.npi_number])
    doc_table = Table(doc_data, colWidths=[2 * inch, 4 * inch])
    doc_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(doc_table)
    story.append(Spacer(1, 0.2 * inch))

    # ── Itemized Charges ──────────────────────────────────────────────────────
    story.append(Paragraph("<b>Itemized Charges</b>", styles['Heading2']))
    if appointment.cpt_code:
        story.append(Paragraph(f"CPT Code: {appointment.cpt_code}", styles['Normal']))
    story.append(Spacer(1, 0.1 * inch))

    item_rows = [["Description", "Amount"]]
    for item in billing_ctx['line_items']:
        item_rows.append([
            Paragraph(f"<b>{item['label']}</b><br/><font size=8 color=grey>{item['description']}</font>", styles['Normal']),
            Paragraph(f"${item['amount']}", right_style),
        ])

    item_rows.append(["", ""])  # spacer row
    item_rows.append([
        Paragraph("<b>Subtotal</b>", styles['Normal']),
        Paragraph(f"<b>${billing_ctx['subtotal']}</b>", right_style),
    ])

    if billing_ctx.get('has_insurance') and billing_ctx['insurance_coverage'] > 0:
        item_rows.append([
            Paragraph(f"Insurance Coverage ({billing_ctx['insurance_provider']})", styles['Normal']),
            Paragraph(f"<font color=green>-${billing_ctx['insurance_coverage']}</font>", right_style),
        ])

    item_rows.append([
        Paragraph("<b>Amount Due</b>", styles['Normal']),
        Paragraph(f"<b>${billing_ctx['amount_due']}</b>", right_style),
    ])

    if billing_ctx['amount_paid'] > 0:
        item_rows.append([
            Paragraph("Amount Paid", styles['Normal']),
            Paragraph(f"<font color=green>-${billing_ctx['amount_paid']}</font>", right_style),
        ])

    if billing_ctx['refund_total'] > 0:
        item_rows.append([
            Paragraph("Refunded", styles['Normal']),
            Paragraph(f"<font color=blue>-${billing_ctx['refund_total']}</font>", right_style),
        ])

    item_rows.append([
        Paragraph("<b>Balance</b>", styles['Normal']),
        Paragraph(f"<b>${billing_ctx['balance']}</b>", right_style),
    ])

    charges_table = Table(item_rows, colWidths=[4.5 * inch, 1.5 * inch])
    charges_table.setStyle(TableStyle([
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e3a8a')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
        ('LINEBELOW', (0, -1), (-1, -1), 1.5, colors.HexColor('#1e3a8a')),
        ('LINEABOVE', (0, -1), (-1, -1), 0.5, colors.lightgrey),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
    ]))
    story.append(charges_table)
    story.append(Spacer(1, 0.3 * inch))

    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.lightgrey))
    story.append(Spacer(1, 0.15 * inch))
    story.append(Paragraph(
        "This document is for insurance and personal records. "
        "Please contact your insurance provider for claim submission. "
        "MedConsult does not process insurance claims directly.",
        styles['Italic']
    ))

    doc.build(story)
    buffer.seek(0)
    return buffer


@transaction.atomic
def set_appointment_cpt_code(appointment, cpt_code):
    """Set the CPT billing code for an appointment."""
    appointment.cpt_code = cpt_code
    appointment.save(update_fields=['cpt_code'])
    return appointment


# ============ REVIEW RESPONSE SERVICES ============

@transaction.atomic
def respond_to_review(review, doctor_profile, response_text):
    """Doctor responds to a patient review."""
    from .models import Review
    if review.doctor != doctor_profile:
        raise ValueError('You can only respond to reviews for your own appointments.')
    if review.response_text:
        raise ValueError('You have already responded to this review.')
    if not response_text.strip():
        raise ValueError('Response text cannot be empty.')
    review.response_text = response_text.strip()
    review.responded_at = timezone.now()
    review.save(update_fields=['response_text', 'responded_at'])
    return review
