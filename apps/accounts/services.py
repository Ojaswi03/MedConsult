"""
Services for accounts app - handles business logic and write operations.
"""
from django.db import transaction
from django.utils import timezone
from django.contrib.sites.shortcuts import get_current_site
from django.urls import reverse
from .models import User, PatientProfile, DoctorProfile, EmailVerificationToken, PasswordResetToken


def create_email_verification_token(user):
    """Create a new email verification token for a user."""
    # Invalidate any existing unused tokens
    EmailVerificationToken.objects.filter(user=user, is_used=False).update(is_used=True)

    # Create new token
    token = EmailVerificationToken.objects.create(user=user)
    return token


def send_verification_email(user, request=None):
    """
    Send email verification email to user.
    Uses Celery for async sending.
    """
    from .tasks import send_verification_email_task

    token = create_email_verification_token(user)

    # Build verification URL
    if request:
        domain = get_current_site(request).domain
        protocol = 'https' if request.is_secure() else 'http'
    else:
        domain = 'localhost:8000'
        protocol = 'http'

    verification_url = f"{protocol}://{domain}{reverse('verify_email', kwargs={'token': token.token})}"

    # Send asynchronously via Celery
    send_verification_email_task.delay(user.id, verification_url)

    return token


def verify_email_token(token_str):
    """
    Verify an email verification token.
    Returns (success, message, user)
    """
    try:
        token = EmailVerificationToken.objects.select_related('user').get(token=token_str)
    except EmailVerificationToken.DoesNotExist:
        return False, "Invalid verification link.", None

    if token.is_used:
        return False, "This verification link has already been used.", None

    if token.is_expired:
        return False, "This verification link has expired. Please request a new one.", None

    # Mark token as used
    token.is_used = True
    token.used_at = timezone.now()
    token.save()

    # Verify user's email
    user = token.user
    user.is_email_verified = True
    user.email_verified_at = timezone.now()
    user.save(update_fields=['is_email_verified', 'email_verified_at'])

    # Send welcome email now that verification is confirmed
    from .tasks import send_welcome_email_task
    send_welcome_email_task.delay(user.id)

    return True, "Email verified successfully!", user


def create_password_reset_token(user):
    """Create a new password reset token for a user."""
    # Invalidate any existing unused tokens
    PasswordResetToken.objects.filter(user=user, is_used=False).update(is_used=True)

    # Create new token
    token = PasswordResetToken.objects.create(user=user)
    return token


def send_password_reset_email(user, request=None):
    """
    Send password reset email to user.
    Uses Celery for async sending.
    """
    from .tasks import send_password_reset_email_task

    token = create_password_reset_token(user)

    # Build reset URL
    if request:
        domain = get_current_site(request).domain
        protocol = 'https' if request.is_secure() else 'http'
    else:
        domain = 'localhost:8000'
        protocol = 'http'

    reset_url = f"{protocol}://{domain}{reverse('reset_password', kwargs={'token': token.token})}"

    # Send asynchronously via Celery
    send_password_reset_email_task.delay(user.id, reset_url)

    return token


def verify_password_reset_token(token_str):
    """
    Verify a password reset token.
    Returns (success, message, token_obj)
    """
    try:
        token = PasswordResetToken.objects.select_related('user').get(token=token_str)
    except PasswordResetToken.DoesNotExist:
        return False, "Invalid password reset link.", None

    if token.is_used:
        return False, "This password reset link has already been used.", None

    if token.is_expired:
        return False, "This password reset link has expired. Please request a new one.", None

    return True, "Token is valid.", token


def reset_user_password(token, new_password):
    """
    Reset user's password using a valid token.
    """
    # Mark token as used
    token.is_used = True
    token.used_at = timezone.now()
    token.save()

    # Update password
    user = token.user
    user.set_password(new_password)
    user.save()

    return user


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


def create_notification(user, notif_type, title, message, link=''):
    """Create an in-app notification for a user."""
    from .models import Notification
    return Notification.objects.create(
        user=user,
        notif_type=notif_type,
        title=title,
        message=message,
        link=link,
    )


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


