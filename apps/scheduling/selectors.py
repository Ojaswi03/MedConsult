"""
Selectors for scheduling app - handles read operations and queries.
"""
from django.utils import timezone
from django.db.models import Q
from .models import Slot, Appointment, AvailabilityWindow


def get_available_slots_for_doctor(doctor_profile, start_date=None, end_date=None):
    """Get all available slots for a doctor within a date range."""
    query = Q(doctor=doctor_profile, is_booked=False, start_datetime__gt=timezone.now())

    if start_date:
        query &= Q(start_datetime__date__gte=start_date)
    if end_date:
        query &= Q(start_datetime__date__lte=end_date)

    return Slot.objects.filter(query).order_by('start_datetime')


def get_doctor_availability_windows(doctor_profile):
    """Get all active availability windows for a doctor."""
    return AvailabilityWindow.objects.filter(
        doctor=doctor_profile,
        is_active=True
    ).order_by('weekday', 'start_time')


def get_patient_appointments(patient, status=None):
    """Get all appointments for a patient, optionally filtered by status."""
    query = Q(patient=patient)

    if status:
        query &= Q(status=status)

    return Appointment.objects.filter(query).select_related(
        'slot', 'doctor__user'
    ).order_by('-slot__start_datetime')


def get_doctor_appointments(doctor_profile, status=None):
    """Get all appointments for a doctor, optionally filtered by status."""
    query = Q(doctor=doctor_profile)

    if status:
        query &= Q(status=status)

    return Appointment.objects.filter(query).select_related(
        'slot', 'patient'
    ).order_by('-slot__start_datetime')


def get_upcoming_patient_appointments(patient):
    """Get upcoming scheduled appointments for a patient."""
    return Appointment.objects.filter(
        patient=patient,
        status='scheduled',
        slot__start_datetime__gt=timezone.now()
    ).select_related('slot', 'doctor__user').order_by('slot__start_datetime')


def get_upcoming_doctor_appointments(doctor_profile):
    """Get upcoming scheduled appointments for a doctor."""
    return Appointment.objects.filter(
        doctor=doctor_profile,
        status='scheduled',
        slot__start_datetime__gt=timezone.now()
    ).select_related('slot', 'patient').order_by('slot__start_datetime')
