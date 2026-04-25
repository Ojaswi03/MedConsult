"""
Selectors for accounts app - handles read operations and queries.
"""
from .models import User, DoctorProfile, PatientProfile


def get_user_profile(user):
    """Get user's profile (patient or doctor)."""
    if user.role == 'patient':
        return PatientProfile.objects.filter(user=user).first()
    elif user.role == 'doctor':
        return DoctorProfile.objects.filter(user=user).first()
    return None


def get_all_verified_doctors():
    """Get all verified doctors."""
    return DoctorProfile.objects.filter(
        verification_status='verified'
    ).select_related('user').order_by('-created_at')


def get_pending_doctor_verifications():
    """Get all doctors pending verification."""
    return DoctorProfile.objects.filter(
        verification_status='pending'
    ).select_related('user').order_by('created_at')


def get_filtered_doctors(
    search=None,
    specialization=None,
    min_rating=None,
    min_experience=None,
    max_experience=None,
    min_price=None,
    max_price=None,
    has_availability=None,
    sort_by='rating',
    language=None,
    available_today=False,
    offers_second_opinions=None,
    group_sessions_only=False,
):
    """
    Get filtered and sorted list of verified doctors.

    Args:
        search: Free text search on name, specialization
        specialization: Exact specialization filter
        min_rating: Minimum average rating (1-5)
        min_experience: Minimum years of experience
        max_experience: Maximum years of experience
        min_price: Minimum consultation fee
        max_price: Maximum consultation fee
        has_availability: Filter by doctors with available slots
        sort_by: Sort order - 'rating', 'experience', 'price_low', 'price_high', 'name'

    Returns:
        QuerySet of DoctorProfile
    """
    from django.db.models import Q, Avg, Count
    from django.utils import timezone
    from datetime import timedelta

    queryset = DoctorProfile.objects.filter(
        verification_status='verified'
    ).select_related('user')

    # Free text search
    if search:
        queryset = queryset.filter(
            Q(user__first_name__icontains=search) |
            Q(user__last_name__icontains=search) |
            Q(specialization__icontains=search) |
            Q(bio__icontains=search)
        )

    # Specialization filter
    if specialization:
        queryset = queryset.filter(specialization__iexact=specialization)

    # Experience filter
    if min_experience is not None:
        queryset = queryset.filter(years_of_experience__gte=min_experience)
    if max_experience is not None:
        queryset = queryset.filter(years_of_experience__lte=max_experience)

    # Price filter
    if min_price is not None:
        queryset = queryset.filter(consultation_fee__gte=min_price)
    if max_price is not None:
        queryset = queryset.filter(consultation_fee__lte=max_price)

    # Annotate with review stats for filtering and sorting
    queryset = queryset.annotate(
        avg_rating=Avg('reviews__rating', filter=Q(reviews__is_visible=True)),
        num_reviews=Count('reviews', filter=Q(reviews__is_visible=True))
    )

    # Rating filter
    if min_rating is not None:
        queryset = queryset.filter(avg_rating__gte=min_rating)

    # Has availability filter - check for available slots in next 14 days
    if has_availability:
        from apps.scheduling.models import Slot
        now = timezone.now()
        end_date = now + timedelta(days=14)
        doctors_with_slots = Slot.objects.filter(
            start_datetime__gte=now,
            start_datetime__lte=end_date,
            is_booked=False,
            is_blocked=False
        ).values_list('doctor_id', flat=True).distinct()
        queryset = queryset.filter(id__in=doctors_with_slots)

    # Language filter
    if language:
        queryset = queryset.filter(languages__icontains=language)

    # Second opinions filter
    if offers_second_opinions is not None:
        queryset = queryset.filter(offers_second_opinions=offers_second_opinions)

    # Group sessions filter — only doctors with at least one available group slot
    if group_sessions_only:
        from apps.scheduling.models import Slot
        now = timezone.now()
        doctors_with_group_slots = Slot.objects.filter(
            start_datetime__gte=now,
            is_booked=False,
            is_blocked=False,
            max_capacity__gt=1,
        ).values_list('doctor_id', flat=True).distinct()
        queryset = queryset.filter(id__in=doctors_with_group_slots)

    # Available today filter
    if available_today:
        from apps.scheduling.models import Slot
        from django.utils import timezone
        today = timezone.now().date()
        doctors_today = Slot.objects.filter(
            start_datetime__date=today,
            is_booked=False,
            is_blocked=False
        ).values_list('doctor_id', flat=True).distinct()
        queryset = queryset.filter(id__in=doctors_today)

    # Sorting
    if sort_by == 'rating':
        queryset = queryset.order_by('-avg_rating', '-num_reviews', '-created_at')
    elif sort_by == 'experience':
        queryset = queryset.order_by('-years_of_experience', '-avg_rating')
    elif sort_by == 'price_low':
        queryset = queryset.order_by('consultation_fee', '-avg_rating')
    elif sort_by == 'price_high':
        queryset = queryset.order_by('-consultation_fee', '-avg_rating')
    elif sort_by == 'name':
        queryset = queryset.order_by('user__first_name', 'user__last_name')
    elif sort_by == 'availability':
        from apps.scheduling.models import Slot
        from django.utils import timezone
        now = timezone.now()
        from django.db.models import Count as AvailCount
        queryset = queryset.annotate(
            avail_slots=AvailCount(
                'slots',
                filter=Q(
                    slots__start_datetime__gt=now,
                    slots__is_booked=False,
                    slots__is_blocked=False
                )
            )
        ).order_by('-avail_slots', '-avg_rating')
    else:
        queryset = queryset.order_by('-avg_rating', '-created_at')

    return queryset


def get_all_specializations():
    """Get list of distinct specializations from verified doctors."""
    return DoctorProfile.objects.filter(
        verification_status='verified'
    ).values_list('specialization', flat=True).distinct().order_by('specialization')


def get_all_languages():
    """Get distinct languages spoken across all verified doctors."""
    import re
    all_langs = DoctorProfile.objects.filter(
        verification_status='verified'
    ).exclude(languages='').values_list('languages', flat=True)
    lang_set = set()
    for lang_string in all_langs:
        for lang in re.split(r'[,;]+', lang_string):
            lang = lang.strip()
            if lang:
                lang_set.add(lang)
    return sorted(lang_set)
