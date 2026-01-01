"""
Services for accounts app - handles business logic and write operations.
"""
from django.db import transaction
from django.utils import timezone
from .models import User, PatientProfile, DoctorProfile


@transaction.atomic
def create_user_with_profile(email, password, username, first_name, last_name, role, **kwargs):
    """Create a user and their associated profile."""
    user = User.objects.create_user(
        email=email,
        password=password,
        username=username,
        first_name=first_name,
        last_name=last_name,
        role=role,
        **kwargs
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


@transaction.atomic
def create_patient_from_wizard(wizard_data: dict) -> User:
    """
    Create a patient user from multi-step wizard data.

    wizard_data structure:
    {
        'step1': {'username', 'email', 'password'},
        'step2': {'first_name', 'middle_name', 'last_name', 'date_of_birth', 'gender', 'gender_other', 'phone'},
        'step3': {'medical_history', 'current_medications', 'allergies'},
        'step4': {'insurance_provider', 'insurance_policy_number'},
        'step5': {'email_notifications', 'phone_notifications', 'terms_accepted'}
    }
    """
    step1 = wizard_data.get('step1', {})
    step2 = wizard_data.get('step2', {})
    step3 = wizard_data.get('step3', {})
    step4 = wizard_data.get('step4', {})
    step5 = wizard_data.get('step5', {})

    # Create user
    user = User.objects.create_user(
        username=step1['username'],
        email=step1['email'],
        password=step1['password'],
        first_name=step2['first_name'],
        middle_name=step2.get('middle_name', ''),
        last_name=step2['last_name'],
        phone=step2.get('phone', ''),
        role='patient',
        email_notifications=step5.get('email_notifications', True),
        phone_notifications=step5.get('phone_notifications', False),
    )

    # Create patient profile
    PatientProfile.objects.create(
        user=user,
        date_of_birth=step2.get('date_of_birth'),
        gender=step2.get('gender', ''),
        gender_other=step2.get('gender_other', ''),
        medical_history=step3.get('medical_history', ''),
        current_medications=step3.get('current_medications', ''),
        allergies=step3.get('allergies', ''),
        insurance_provider=step4.get('insurance_provider', ''),
        insurance_policy_number=step4.get('insurance_policy_number', ''),
        terms_accepted=step5.get('terms_accepted', False),
        terms_accepted_at=timezone.now() if step5.get('terms_accepted') else None,
    )

    return user


@transaction.atomic
def create_doctor_from_wizard(wizard_data: dict, files: dict = None) -> User:
    """
    Create a doctor user from multi-step wizard data.

    wizard_data structure:
    {
        'step1': {'username', 'email', 'password'},
        'step2': {'first_name', 'middle_name', 'last_name', 'date_of_birth', 'gender', 'gender_other', 'phone'},
        'step3': {'medical_license_number', 'education', 'specialization', 'years_of_experience'},
        'step4': {'bank_name', 'account_holder_name', 'account_number', 'routing_number'},
        'step5': {},  # Just government_id_document file
        'step6': {'hipaa_acknowledged', 'terms_accepted'}
    }

    files structure:
    {
        'medical_license_document': UploadedFile,
        'government_id_document': UploadedFile
    }
    """
    files = files or {}
    step1 = wizard_data.get('step1', {})
    step2 = wizard_data.get('step2', {})
    step3 = wizard_data.get('step3', {})
    step4 = wizard_data.get('step4', {})
    step6 = wizard_data.get('step6', {})

    # Create user
    user = User.objects.create_user(
        username=step1['username'],
        email=step1['email'],
        password=step1['password'],
        first_name=step2['first_name'],
        middle_name=step2.get('middle_name', ''),
        last_name=step2['last_name'],
        phone=step2.get('phone', ''),
        role='doctor',
    )

    # Create doctor profile
    profile = DoctorProfile.objects.create(
        user=user,
        date_of_birth=step2.get('date_of_birth'),
        gender=step2.get('gender', ''),
        gender_other=step2.get('gender_other', ''),
        medical_license_number=step3.get('medical_license_number', ''),
        education=step3.get('education', ''),
        specialization=step3.get('specialization', ''),
        years_of_experience=step3.get('years_of_experience', 0),
        bank_name=step4.get('bank_name', ''),
        account_holder_name=step4.get('account_holder_name', ''),
        account_number=step4.get('account_number', ''),
        routing_number=step4.get('routing_number', ''),
        hipaa_acknowledged=step6.get('hipaa_acknowledged', False),
        hipaa_acknowledged_at=timezone.now() if step6.get('hipaa_acknowledged') else None,
        terms_accepted=step6.get('terms_accepted', False),
        terms_accepted_at=timezone.now() if step6.get('terms_accepted') else None,
        verification_status='pending',
    )

    # Handle file uploads
    if 'medical_license_document' in files and files['medical_license_document']:
        profile.medical_license_document = files['medical_license_document']
    if 'government_id_document' in files and files['government_id_document']:
        profile.government_id_document = files['government_id_document']

    profile.save()

    return user


def clear_signup_session(request):
    """Clear all signup wizard data from session."""
    keys_to_delete = [
        'patient_wizard_data',
        'doctor_wizard_data',
        'doctor_wizard_files',
    ]
    for key in keys_to_delete:
        if key in request.session:
            del request.session[key]


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
