"""
Services for scheduling app - handles slot generation and booking logic.
"""
from datetime import datetime, timedelta, time
from django.db import transaction
from django.utils import timezone
from .models import AvailabilityWindow, Slot, Appointment


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
