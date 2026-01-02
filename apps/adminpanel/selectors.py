"""
Selectors for adminpanel app - handles analytics and read operations.
"""
from datetime import timedelta
from django.utils import timezone
from django.db.models import Count, Q, F
from django.db.models.functions import TruncDate

from apps.accounts.models import User, DoctorProfile, PatientProfile
from apps.scheduling.models import Appointment, Slot, SlotChangeLog, AppointmentTypeConfig
from .models import AdminActivityLog


# ============ DASHBOARD ANALYTICS ============

def get_dashboard_overview():
    """Get key metrics for admin dashboard."""
    now = timezone.now()
    thirty_days_ago = now - timedelta(days=30)
    seven_days_ago = now - timedelta(days=7)

    total_appointments = Appointment.objects.count()
    completed_appointments = Appointment.objects.filter(status='completed').count()

    return {
        'total_users': User.objects.count(),
        'total_patients': User.objects.filter(role='patient').count(),
        'total_doctors': User.objects.filter(role='doctor').count(),
        'verified_doctors': DoctorProfile.objects.filter(verification_status='verified').count(),
        'pending_verifications': DoctorProfile.objects.filter(verification_status='pending').count(),
        'total_appointments': total_appointments,
        'scheduled_appointments': Appointment.objects.filter(status='scheduled').count(),
        'completed_appointments': completed_appointments,
        'cancelled_appointments': Appointment.objects.filter(status='cancelled').count(),
        'new_users_30d': User.objects.filter(created_at__gte=thirty_days_ago).count(),
        'new_users_7d': User.objects.filter(created_at__gte=seven_days_ago).count(),
        'appointments_30d': Appointment.objects.filter(created_at__gte=thirty_days_ago).count(),
        'completion_rate': round((completed_appointments / total_appointments * 100) if total_appointments > 0 else 0, 1),
    }


def get_user_growth_data(days=30):
    """Get user registration data for chart visualization."""
    start_date = timezone.now() - timedelta(days=days)

    users_by_date = User.objects.filter(
        created_at__gte=start_date
    ).annotate(
        date=TruncDate('created_at')
    ).values('date', 'role').annotate(
        count=Count('id')
    ).order_by('date')

    return list(users_by_date)


def get_appointment_stats_by_type():
    """Get appointment statistics grouped by type."""
    return list(Appointment.objects.values(
        'slot__appointment_type'
    ).annotate(
        count=Count('id'),
        completed=Count('id', filter=Q(status='completed')),
        cancelled=Count('id', filter=Q(status='cancelled')),
        no_show=Count('id', filter=Q(status='no_show')),
    ).order_by('-count'))


def get_appointment_stats_by_status():
    """Get appointment count by status."""
    return list(Appointment.objects.values('status').annotate(
        count=Count('id')
    ).order_by('status'))


def get_revenue_potential_by_doctor(limit=20):
    """Calculate potential revenue by doctor (completed appointments * fee)."""
    return DoctorProfile.objects.filter(
        verification_status='verified'
    ).annotate(
        total_appointments=Count('doctor_appointments'),
        completed_appointments=Count('doctor_appointments', filter=Q(doctor_appointments__status='completed')),
    ).select_related('user').order_by('-completed_appointments')[:limit]


def get_activity_feed(limit=20):
    """Get recent activity feed combining various sources."""
    # Recent pending doctors (for verification)
    pending_doctors = DoctorProfile.objects.filter(
        verification_status='pending'
    ).select_related('user').order_by('-created_at')[:limit]

    # Recent appointments
    recent_appointments = Appointment.objects.select_related(
        'patient', 'doctor__user', 'slot'
    ).order_by('-created_at')[:limit]

    # Recent slot changes
    recent_slot_changes = SlotChangeLog.objects.select_related(
        'doctor__user'
    ).order_by('-created_at')[:limit]

    # Recent admin actions
    recent_admin_actions = AdminActivityLog.objects.select_related(
        'admin', 'target_user'
    ).order_by('-created_at')[:limit]

    return {
        'pending_doctors': pending_doctors,
        'appointments': recent_appointments,
        'slot_changes': recent_slot_changes,
        'admin_actions': recent_admin_actions,
    }


# ============ USER MANAGEMENT ============

def get_users_filtered(
    role=None,
    is_active=None,
    search_query=None,
    date_from=None,
    date_to=None,
    order_by='-created_at',
    limit=50,
    offset=0
):
    """Get filtered users with pagination."""
    query = Q()

    if role:
        query &= Q(role=role)
    if is_active is not None:
        query &= Q(is_active=is_active)
    if search_query:
        query &= (
            Q(email__icontains=search_query) |
            Q(username__icontains=search_query) |
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query)
        )
    if date_from:
        query &= Q(created_at__date__gte=date_from)
    if date_to:
        query &= Q(created_at__date__lte=date_to)

    total = User.objects.filter(query).count()
    users = User.objects.filter(query).order_by(order_by)[offset:offset + limit]

    return {
        'users': users,
        'total': total,
        'has_more': (offset + limit) < total,
    }


def get_user_detail(user_id):
    """Get detailed user info with profile."""
    user = User.objects.get(id=user_id)
    profile = None
    appointments = []
    stats = {}

    if user.role == 'patient':
        profile = PatientProfile.objects.filter(user=user).first()
        appointments = Appointment.objects.filter(patient=user).select_related(
            'doctor__user', 'slot'
        ).order_by('-created_at')[:10]
        stats = {
            'total_appointments': Appointment.objects.filter(patient=user).count(),
            'completed': Appointment.objects.filter(patient=user, status='completed').count(),
            'cancelled': Appointment.objects.filter(patient=user, status='cancelled').count(),
        }
    elif user.role == 'doctor':
        profile = DoctorProfile.objects.filter(user=user).first()
        appointments = Appointment.objects.filter(doctor__user=user).select_related(
            'patient', 'slot'
        ).order_by('-created_at')[:10]
        if profile:
            stats = {
                'total_appointments': Appointment.objects.filter(doctor=profile).count(),
                'completed': Appointment.objects.filter(doctor=profile, status='completed').count(),
                'total_slots': Slot.objects.filter(doctor=profile).count(),
                'available_slots': Slot.objects.filter(
                    doctor=profile, is_booked=False, is_blocked=False,
                    start_datetime__gt=timezone.now()
                ).count(),
            }

    return {
        'user': user,
        'profile': profile,
        'appointments': appointments,
        'stats': stats,
    }


# ============ DOCTOR MANAGEMENT ============

def get_pending_doctors_detailed():
    """Get pending doctors with full details for verification."""
    return DoctorProfile.objects.filter(
        verification_status='pending'
    ).select_related('user').order_by('created_at')


def get_doctor_statistics(doctor_id):
    """Get comprehensive statistics for a doctor."""
    doctor = DoctorProfile.objects.select_related('user').get(id=doctor_id)
    now = timezone.now()
    thirty_days_ago = now - timedelta(days=30)

    slots = Slot.objects.filter(doctor=doctor)
    appointments = Appointment.objects.filter(doctor=doctor)

    completed_count = appointments.filter(status='completed').count()
    potential_revenue = completed_count * doctor.consultation_fee if doctor.consultation_fee else 0

    return {
        'doctor': doctor,
        'total_slots': slots.count(),
        'available_slots': slots.filter(is_booked=False, is_blocked=False, start_datetime__gt=now).count(),
        'booked_slots': slots.filter(is_booked=True).count(),
        'blocked_slots': slots.filter(is_blocked=True).count(),
        'total_appointments': appointments.count(),
        'completed_appointments': completed_count,
        'cancelled_appointments': appointments.filter(status='cancelled').count(),
        'no_show_appointments': appointments.filter(status='no_show').count(),
        'appointments_30d': appointments.filter(created_at__gte=thirty_days_ago).count(),
        'potential_revenue': potential_revenue,
    }


def get_all_doctors_with_stats():
    """Get all doctors with their statistics."""
    now = timezone.now()
    return DoctorProfile.objects.annotate(
        total_appointments=Count('doctor_appointments'),
        completed_appointments=Count('doctor_appointments', filter=Q(doctor_appointments__status='completed')),
        total_slots=Count('slots'),
        available_slots=Count('slots', filter=Q(
            slots__is_booked=False,
            slots__is_blocked=False,
            slots__start_datetime__gt=now
        ))
    ).select_related('user').order_by('-created_at')


# ============ APPOINTMENT MANAGEMENT ============

def get_appointments_filtered(
    status=None,
    appointment_type=None,
    doctor_id=None,
    patient_id=None,
    date_from=None,
    date_to=None,
    search_query=None,
    order_by='-created_at',
    limit=50,
    offset=0
):
    """Get filtered appointments with pagination."""
    query = Q()

    if status:
        query &= Q(status=status)
    if appointment_type:
        query &= Q(slot__appointment_type=appointment_type)
    if doctor_id:
        query &= Q(doctor_id=doctor_id)
    if patient_id:
        query &= Q(patient_id=patient_id)
    if date_from:
        query &= Q(slot__start_datetime__date__gte=date_from)
    if date_to:
        query &= Q(slot__start_datetime__date__lte=date_to)
    if search_query:
        query &= (
            Q(patient__email__icontains=search_query) |
            Q(patient__first_name__icontains=search_query) |
            Q(patient__last_name__icontains=search_query) |
            Q(doctor__user__email__icontains=search_query) |
            Q(doctor__user__first_name__icontains=search_query) |
            Q(doctor__user__last_name__icontains=search_query)
        )

    total = Appointment.objects.filter(query).count()
    appointments = Appointment.objects.filter(query).select_related(
        'patient', 'doctor__user', 'slot'
    ).order_by(order_by)[offset:offset + limit]

    return {
        'appointments': appointments,
        'total': total,
        'has_more': (offset + limit) < total,
    }


def get_appointments_calendar_data(start_date, end_date):
    """Get appointments for calendar view."""
    return Appointment.objects.filter(
        slot__start_datetime__date__gte=start_date,
        slot__start_datetime__date__lte=end_date
    ).select_related('patient', 'doctor__user', 'slot').order_by('slot__start_datetime')


# ============ FINANCIAL OVERVIEW ============

def get_pricing_overview():
    """Get appointment type pricing across all doctors."""
    return AppointmentTypeConfig.objects.filter(
        is_enabled=True
    ).select_related('doctor__user').order_by('doctor', 'appointment_type')


def get_appointment_type_usage():
    """Get usage statistics by appointment type."""
    return list(Appointment.objects.values(
        'slot__appointment_type'
    ).annotate(
        total=Count('id'),
        completed=Count('id', filter=Q(status='completed')),
        cancelled=Count('id', filter=Q(status='cancelled')),
    ).order_by('-total'))


def get_revenue_summary():
    """Get overall revenue summary."""
    completed_appointments = Appointment.objects.filter(
        status='completed'
    ).select_related('doctor')

    total_revenue = 0
    for apt in completed_appointments:
        if apt.doctor and apt.doctor.consultation_fee:
            total_revenue += apt.doctor.consultation_fee

    return {
        'total_completed': completed_appointments.count(),
        'total_potential_revenue': total_revenue,
    }


# ============ AUDIT & ACTIVITY ============

def get_slot_change_logs(
    doctor_id=None,
    change_type=None,
    date_from=None,
    date_to=None,
    limit=100,
    offset=0
):
    """Get slot change logs with filters."""
    query = Q()

    if doctor_id:
        query &= Q(doctor_id=doctor_id)
    if change_type:
        query &= Q(change_type=change_type)
    if date_from:
        query &= Q(created_at__date__gte=date_from)
    if date_to:
        query &= Q(created_at__date__lte=date_to)

    total = SlotChangeLog.objects.filter(query).count()
    logs = SlotChangeLog.objects.filter(query).select_related(
        'doctor__user', 'slot'
    ).order_by('-created_at')[offset:offset + limit]

    return {
        'logs': logs,
        'total': total,
        'has_more': (offset + limit) < total,
    }


def get_admin_activity_logs(
    admin_id=None,
    action_type=None,
    date_from=None,
    date_to=None,
    limit=100,
    offset=0
):
    """Get admin activity logs with filters."""
    query = Q()

    if admin_id:
        query &= Q(admin_id=admin_id)
    if action_type:
        query &= Q(action_type=action_type)
    if date_from:
        query &= Q(created_at__date__gte=date_from)
    if date_to:
        query &= Q(created_at__date__lte=date_to)

    total = AdminActivityLog.objects.filter(query).count()
    logs = AdminActivityLog.objects.filter(query).select_related(
        'admin', 'target_user'
    ).order_by('-created_at')[offset:offset + limit]

    return {
        'logs': logs,
        'total': total,
        'has_more': (offset + limit) < total,
    }
