"""
Services for accounts app - handles business logic and write operations.
"""
from django.db import transaction
from .models import User, PatientProfile, DoctorProfile


@transaction.atomic
def create_user_with_profile(email, password, first_name, last_name, role):
    """Create a user and their associated profile."""
    user = User.objects.create_user(
        email=email,
        password=password,
        first_name=first_name,
        last_name=last_name,
        role=role
    )

    # Create profile based on role
    if role == 'patient':
        PatientProfile.objects.create(user=user)
    elif role == 'doctor':
        DoctorProfile.objects.create(
            user=user,
            medical_license_number='',
            specialization='General Practice'
        )

    return user


def update_patient_profile(profile, **kwargs):
    """Update patient profile."""
    for key, value in kwargs.items():
        setattr(profile, key, value)
    profile.save()
    return profile


def update_doctor_profile(profile, **kwargs):
    """Update doctor profile."""
    for key, value in kwargs.items():
        setattr(profile, key, value)
    profile.save()
    return profile
