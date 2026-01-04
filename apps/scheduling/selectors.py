"""
Selectors for scheduling app - handles read operations and queries.
"""
from datetime import timedelta
from django.utils import timezone
from django.db.models import Q, Count
from .models import Slot, Appointment, AvailabilityWindow, SlotChangeLog, AppointmentTypeConfig


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


# ============ CALENDAR AND AVAILABILITY SELECTORS ============

def get_doctor_slots_for_calendar(doctor_profile, start_date, end_date):
    """
    Get all slots for a doctor within date range for calendar display.
    Returns slots with status information for color-coding.
    """
    return Slot.objects.filter(
        doctor=doctor_profile,
        start_datetime__date__gte=start_date,
        start_datetime__date__lte=end_date
    ).select_related('availability_window').order_by('start_datetime')


def get_slots_grouped_by_date(doctor_profile, start_date=None, end_date=None):
    """Get slots grouped by date for weekly/monthly views."""
    if not start_date:
        start_date = timezone.now().date()
    if not end_date:
        end_date = start_date + timedelta(days=30)

    slots = get_doctor_slots_for_calendar(doctor_profile, start_date, end_date)

    grouped = {}
    for slot in slots:
        date_key = slot.start_datetime.date()
        if date_key not in grouped:
            grouped[date_key] = []
        grouped[date_key].append(slot)

    return grouped


def get_slots_grouped_by_day_of_week(doctor_profile, start_date, end_date):
    """
    Get slots grouped by day of week for weekly calendar view.
    Returns dict with weekday index (0=Monday) as keys.
    """
    slots = get_doctor_slots_for_calendar(doctor_profile, start_date, end_date)

    grouped = {i: [] for i in range(7)}  # 0-6 for Mon-Sun
    for slot in slots:
        day_index = slot.start_datetime.weekday()
        grouped[day_index].append(slot)

    return grouped


def get_available_slots_by_type(doctor_profile, appointment_type, start_date=None, end_date=None):
    """Get available slots filtered by appointment type."""
    query = Q(
        doctor=doctor_profile,
        is_booked=False,
        is_blocked=False,
        start_datetime__gt=timezone.now(),
        appointment_type=appointment_type
    )

    if start_date:
        query &= Q(start_datetime__date__gte=start_date)
    if end_date:
        query &= Q(start_datetime__date__lte=end_date)

    return Slot.objects.filter(query).order_by('start_datetime')


def get_all_availability_windows(doctor_profile, include_inactive=False):
    """Get all availability windows for a doctor."""
    query = Q(doctor=doctor_profile)
    if not include_inactive:
        query &= Q(is_active=True)

    return AvailabilityWindow.objects.filter(query).order_by('weekday', 'start_time')


def get_availability_summary(doctor_profile):
    """Get summary statistics for doctor's availability."""
    now = timezone.now()
    next_30_days = now + timedelta(days=30)

    slots = Slot.objects.filter(
        doctor=doctor_profile,
        start_datetime__gte=now,
        start_datetime__lte=next_30_days
    )

    return {
        'total_slots': slots.count(),
        'available_slots': slots.filter(is_booked=False, is_blocked=False).count(),
        'booked_slots': slots.filter(is_booked=True).count(),
        'blocked_slots': slots.filter(is_blocked=True).count(),
        'urgent_slots': slots.filter(is_urgent=True, is_booked=False).count(),
    }


# ============ REAL-TIME UPDATE SELECTORS ============

def get_slot_changes_since(doctor_profile, since_timestamp):
    """Get all slot changes since a given timestamp for real-time updates."""
    return SlotChangeLog.objects.filter(
        doctor=doctor_profile,
        created_at__gt=since_timestamp
    ).order_by('created_at')


def has_slot_changes_since(doctor_profile, since_timestamp):
    """Check if there are any slot changes since a given timestamp."""
    return SlotChangeLog.objects.filter(
        doctor=doctor_profile,
        created_at__gt=since_timestamp
    ).exists()


# ============ PATIENT VIEW SELECTORS ============

def get_slots_for_patient_view(doctor_profile, start_date=None, days_ahead=14):
    """
    Get available slots for patient booking view.
    Groups by date and filters to only available slots.
    """
    if not start_date:
        start_date = timezone.now().date()
    end_date = start_date + timedelta(days=days_ahead)

    slots = Slot.objects.filter(
        doctor=doctor_profile,
        start_datetime__date__gte=start_date,
        start_datetime__date__lte=end_date,
        start_datetime__gt=timezone.now(),
        is_booked=False,
        is_blocked=False
    ).order_by('start_datetime')

    # Group by date
    grouped = {}
    for slot in slots:
        date_key = slot.start_datetime.date()
        if date_key not in grouped:
            grouped[date_key] = []

        # Check availability for group sessions
        if slot.max_capacity > 1:
            if slot.current_bookings < slot.max_capacity:
                grouped[date_key].append(slot)
        else:
            grouped[date_key].append(slot)

    return grouped


def get_slots_for_patient_by_type(doctor_profile, appointment_type=None, days_ahead=14):
    """
    Get available slots for patient, optionally filtered by appointment type.
    """
    start_date = timezone.now().date()
    end_date = start_date + timedelta(days=days_ahead)

    query = Q(
        doctor=doctor_profile,
        start_datetime__date__gte=start_date,
        start_datetime__date__lte=end_date,
        start_datetime__gt=timezone.now(),
        is_booked=False,
        is_blocked=False
    )

    if appointment_type:
        query &= Q(appointment_type=appointment_type)

    return Slot.objects.filter(query).order_by('start_datetime')


# ============ APPOINTMENT TYPE CONFIG SELECTORS ============

def get_doctor_appointment_type_configs(doctor_profile):
    """Get appointment type configurations for a doctor."""
    return AppointmentTypeConfig.objects.filter(
        doctor=doctor_profile
    ).order_by('appointment_type')


def get_enabled_appointment_types(doctor_profile):
    """Get only enabled appointment types for a doctor."""
    return AppointmentTypeConfig.objects.filter(
        doctor=doctor_profile,
        is_enabled=True
    ).order_by('appointment_type')


def get_appointment_type_price(doctor_profile, appointment_type):
    """Get price for a specific appointment type."""
    config = AppointmentTypeConfig.objects.filter(
        doctor=doctor_profile,
        appointment_type=appointment_type,
        is_enabled=True
    ).first()

    if config:
        return config.price
    return None


# ============ REVIEW SELECTORS ============

def get_doctor_reviews(doctor_profile, limit=None):
    """Get all visible reviews for a doctor, most recent first."""
    from .models import Review

    query = Review.objects.filter(
        doctor=doctor_profile,
        is_visible=True
    ).select_related('patient', 'appointment__slot').order_by('-created_at')

    if limit:
        query = query[:limit]

    return query


def get_patient_reviewable_appointments(patient):
    """Get completed appointments that the patient can still review."""
    from .models import Appointment, Review

    # Get completed appointments without reviews
    reviewed_appointment_ids = Review.objects.filter(
        patient=patient
    ).values_list('appointment_id', flat=True)

    return Appointment.objects.filter(
        patient=patient,
        status='completed'
    ).exclude(
        id__in=reviewed_appointment_ids
    ).select_related('doctor__user', 'slot').order_by('-slot__start_datetime')


def get_review_by_appointment(appointment):
    """Get review for a specific appointment if it exists."""
    from .models import Review

    return Review.objects.filter(appointment=appointment).first()


def can_patient_review_appointment(patient, appointment):
    """Check if a patient can review a specific appointment."""
    from .models import Review

    # Must be the patient who had the appointment
    if appointment.patient != patient:
        return False

    # Appointment must be completed
    if appointment.status != 'completed':
        return False

    # No existing review
    return not Review.objects.filter(appointment=appointment).exists()
