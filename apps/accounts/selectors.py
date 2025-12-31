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


def get_doctors_by_specialization(specialization):
    """Get verified doctors by specialization."""
    return DoctorProfile.objects.filter(
        verification_status='verified',
        specialization__icontains=specialization
    ).select_related('user')


def get_pending_doctor_verifications():
    """Get all doctors pending verification."""
    return DoctorProfile.objects.filter(
        verification_status='pending'
    ).select_related('user').order_by('created_at')
