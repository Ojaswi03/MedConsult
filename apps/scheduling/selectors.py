"""
Selectors for scheduling app - handles read operations and queries.
"""
from datetime import timedelta
from django.utils import timezone
from django.db.models import Q, Count
from .models import Slot, Appointment, AvailabilityWindow, SlotChangeLog, AppointmentTypeConfig
from apps.accounts.query_utils import scope_to_org


def get_available_slots_for_doctor(doctor_profile, organization=None, start_date=None, end_date=None):
    """Get available slots for a doctor, optionally scoped to an org."""
    query = Q(doctor=doctor_profile, is_booked=False, start_datetime__gt=timezone.now())
    if start_date:
        query &= Q(start_datetime__date__gte=start_date)
    if end_date:
        query &= Q(start_datetime__date__lte=end_date)
    qs = Slot.objects.filter(query).order_by('start_datetime')
    if organization is not None:
        qs = qs.filter(organization=organization)
    return qs


def get_doctor_availability_windows(doctor_profile, organization=None):
    """Get active availability windows for a doctor, optionally scoped to an org."""
    query = Q(doctor=doctor_profile, is_active=True)
    if organization is not None:
        query &= Q(organization=organization)
    return AvailabilityWindow.objects.filter(query).order_by('weekday', 'start_time')


def get_patient_appointments(patient, status=None):
    """Patient-owned — scoped by patient FK only, never by org."""
    query = Q(patient=patient)
    if status:
        query &= Q(status=status)
    return Appointment.objects.filter(query).select_related(
        'slot', 'doctor__user',
    ).order_by('-slot__start_datetime')


def get_doctor_appointments(doctor_profile, organization=None, status=None, user=None):
    """Get appointments for a doctor, optionally scoped to an org."""
    query = Q(doctor=doctor_profile)
    if status:
        query &= Q(status=status)
    qs = Appointment.objects.filter(query).select_related('slot', 'patient')
    qs = scope_to_org(qs, organization, user)
    return qs.order_by('-slot__start_datetime')


def get_appointment_by_id(appointment_id, organization=None, user=None):
    """Fetch a single appointment; prevents cross-org IDOR when org provided."""
    qs = Appointment.objects.filter(id=appointment_id)
    return scope_to_org(qs, organization, user).first()


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


# ============ APPOINTMENT TYPE CONFIG SELECTORS ============

def get_enabled_appointment_types(doctor_profile):
    """Get only enabled appointment types for a doctor."""
    return AppointmentTypeConfig.objects.filter(
        doctor=doctor_profile,
        is_enabled=True
    ).order_by('appointment_type')


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


def get_prescription_for_appointment(appointment):
    """Get prescription for an appointment if it exists."""
    from .models import Prescription
    return Prescription.objects.filter(appointment=appointment).first()


def get_doctor_time_off_blocks(doctor_profile):
    """Get all time-off blocks for a doctor."""
    from .models import TimeOffBlock
    return TimeOffBlock.objects.filter(doctor=doctor_profile).order_by('start_date')


def get_patient_history_for_doctor(patient, doctor_profile):
    """Doctor's view of a patient's history with them."""
    from .models import Prescription
    from apps.scheduling.services import get_shared_records_for_doctor
    appointments = Appointment.objects.filter(
        patient=patient, doctor=doctor_profile
    ).select_related('slot').order_by('-slot__start_datetime')

    return {
        'appointments': appointments,
        'total': appointments.count(),
        'completed': appointments.filter(status='completed').count(),
        'prescriptions': Prescription.objects.filter(patient=patient, doctor=doctor_profile).order_by('-created_at'),
        'shared_records': get_shared_records_for_doctor(doctor_profile, patient),
    }


def get_doctor_analytics(doctor_profile):
    """Get analytics data for doctor dashboard."""
    from django.db.models import Count, Avg
    from django.db.models.functions import TruncMonth, TruncDate
    from datetime import timedelta

    now = timezone.now()
    six_months_ago = now - timedelta(days=180)

    appointments = Appointment.objects.filter(doctor=doctor_profile)
    total = appointments.count()
    completed = appointments.filter(status='completed').count()
    cancelled = appointments.filter(status='cancelled').count()
    scheduled = appointments.filter(status='scheduled').count()

    # Monthly volume (last 6 months)
    monthly = list(
        appointments.filter(created_at__gte=six_months_ago)
        .annotate(month=TruncMonth('created_at'))
        .values('month')
        .annotate(count=Count('id'))
        .order_by('month')
    )

    # Busiest days of week
    from django.db.models.functions import ExtractWeekDay
    busiest_days_qs = list(
        appointments.filter(status='completed')
        .annotate(weekday=ExtractWeekDay('slot__start_datetime'))
        .values('weekday')
        .annotate(count=Count('id'))
        .order_by('weekday')
    )
    day_names = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
    busiest_days = [
        {'day': day_names[d['weekday'] - 1], 'count': d['count']}
        for d in busiest_days_qs
    ]

    # Appointment type breakdown
    type_breakdown = list(
        appointments.values('slot__appointment_type')
        .annotate(count=Count('id'))
        .order_by('-count')
    )

    # Rating info
    from .models import Review
    reviews = Review.objects.filter(doctor=doctor_profile, is_visible=True)
    avg_rating = reviews.aggregate(Avg('rating'))['rating__avg'] or 0
    review_count = reviews.count()

    # Recent rating trend (last 10 reviews)
    recent_reviews = list(
        reviews.order_by('-created_at')[:10]
        .values('rating', 'created_at')
    )

    # Slots summary
    slots = Slot.objects.filter(doctor=doctor_profile)
    upcoming_available = slots.filter(
        is_booked=False, is_blocked=False, start_datetime__gt=now
    ).count()

    return {
        'total_appointments': total,
        'completed_appointments': completed,
        'cancelled_appointments': cancelled,
        'scheduled_appointments': scheduled,
        'completion_rate': round((completed / total * 100) if total > 0 else 0, 1),
        'monthly_volume': monthly,
        'busiest_days': busiest_days,
        'type_breakdown': type_breakdown,
        'avg_rating': round(float(avg_rating), 1),
        'review_count': review_count,
        'recent_reviews': recent_reviews,
        'upcoming_available_slots': upcoming_available,
    }


def get_availability_exceptions(doctor_profile):
    """Get all availability exceptions for a doctor."""
    from .models import AvailabilityException
    return AvailabilityException.objects.filter(doctor=doctor_profile).order_by('date')


def get_patient_dashboard_data(patient):
    """Get all data needed for the patient dashboard."""
    from .models import Referral
    from apps.accounts.models import Notification

    now = timezone.now()

    upcoming = Appointment.objects.filter(
        patient=patient,
        status='scheduled',
        slot__start_datetime__gt=now
    ).select_related('slot', 'doctor__user').order_by('slot__start_datetime')[:5]

    pending_reviews = get_patient_reviewable_appointments(patient)[:3]

    active_referrals = Referral.objects.filter(
        patient=patient, status__in=['pending', 'accepted']
    ).select_related('referred_to_doctor__user', 'referring_doctor__user').order_by('-created_at')[:5]

    recent_notifs = Notification.objects.filter(
        user=patient, is_read=False
    ).order_by('-created_at')[:5]

    # Distinct past doctors for "Book again" feature
    from django.db.models import Max
    past_appointments = Appointment.objects.filter(
        patient=patient, status='completed'
    ).select_related('doctor__user').order_by('-slot__start_datetime')

    seen_doctors = {}
    for appt in past_appointments:
        if appt.doctor_id not in seen_doctors:
            seen_doctors[appt.doctor_id] = appt.doctor
        if len(seen_doctors) >= 5:
            break

    return {
        'upcoming_appointments': upcoming,
        'pending_reviews': pending_reviews,
        'active_referrals': active_referrals,
        'recent_notifications': recent_notifs,
        'book_again_doctors': list(seen_doctors.values()),
    }


def get_insurance_breakdown_for_admin():
    """Get appointment counts and totals grouped by insurance provider."""
    from django.db.models import Count, Sum
    from apps.accounts.models import PatientProfile

    results = []
    providers = PatientProfile.objects.exclude(
        insurance_provider=''
    ).values('insurance_provider').distinct()

    for p in providers:
        provider = p['insurance_provider']
        patients_with_provider = PatientProfile.objects.filter(
            insurance_provider=provider
        ).values_list('user_id', flat=True)
        count = Appointment.objects.filter(
            patient_id__in=patients_with_provider,
            status='completed'
        ).count()
        results.append({'provider': provider, 'completed_appointments': count})

    return sorted(results, key=lambda x: x['completed_appointments'], reverse=True)
