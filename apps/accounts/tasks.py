"""
Celery tasks for accounts app - async email sending.
"""
from celery import shared_task
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings


@shared_task(bind=True, max_retries=3)
def send_verification_email_task(self, user_id, verification_url):
    """
    Send email verification email asynchronously.
    """
    from .models import User

    try:
        user = User.objects.get(id=user_id)

        subject = 'Verify your MedConsult email address'
        html_message = render_to_string('accounts/emails/verify_email.html', {
            'user': user,
            'verification_url': verification_url,
        })
        plain_message = f"""
Hi {user.first_name or user.username},

Please verify your email address by clicking the link below:

{verification_url}

This link will expire in 24 hours.

If you didn't create an account on MedConsult, please ignore this email.

Best regards,
The MedConsult Team
        """

        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )

        return f"Verification email sent to {user.email}"

    except User.DoesNotExist:
        return f"User {user_id} not found"
    except Exception as exc:
        self.retry(exc=exc, countdown=60)


@shared_task(bind=True, max_retries=3)
def send_password_reset_email_task(self, user_id, reset_url):
    """
    Send password reset email asynchronously.
    """
    from .models import User

    try:
        user = User.objects.get(id=user_id)

        subject = 'Reset your MedConsult password'
        html_message = render_to_string('accounts/emails/password_reset.html', {
            'user': user,
            'reset_url': reset_url,
        })
        plain_message = f"""
Hi {user.first_name or user.username},

We received a request to reset your password. Click the link below to set a new password:

{reset_url}

This link will expire in 1 hour.

If you didn't request a password reset, please ignore this email. Your password will remain unchanged.

Best regards,
The MedConsult Team
        """

        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )

        return f"Password reset email sent to {user.email}"

    except User.DoesNotExist:
        return f"User {user_id} not found"
    except Exception as exc:
        self.retry(exc=exc, countdown=60)


@shared_task(bind=True, max_retries=3)
def send_welcome_email_task(self, user_id):
    """
    Send welcome email after successful registration.
    """
    from .models import User

    try:
        user = User.objects.get(id=user_id)

        subject = 'Welcome to MedConsult!'
        html_message = render_to_string('accounts/emails/welcome.html', {
            'user': user,
        })
        plain_message = f"""
Hi {user.first_name or user.username},

Welcome to MedConsult! Your account has been created successfully.

{'Your account is pending verification. You will be notified once verified.' if user.role == 'doctor' else 'You can now book appointments with our verified doctors.'}

Best regards,
The MedConsult Team
        """

        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )

        return f"Welcome email sent to {user.email}"

    except User.DoesNotExist:
        return f"User {user_id} not found"
    except Exception as exc:
        self.retry(exc=exc, countdown=60)


@shared_task(bind=True, max_retries=3)
def send_doctor_rejection_email_task(self, doctor_user_id, reason=''):
    """Send email to a doctor when their verification is rejected."""
    from .models import User

    try:
        user = User.objects.get(id=doctor_user_id)

        subject = 'Update on your MedConsult verification application'
        html_message = render_to_string('accounts/emails/doctor_rejected.html', {
            'user': user,
            'reason': reason,
        })
        plain_message = f"""
Hi {user.first_name or user.username},

Thank you for applying to join MedConsult as a healthcare provider.

After reviewing your application, we were unable to verify your credentials at this time.

{"Reason: " + reason if reason else "Please ensure your documents are clear, valid, and unexpired."}

You are welcome to reapply with updated documents. If you believe this decision was made in error, please contact our support team.

Best regards,
The MedConsult Team
        """

        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )

        return f"Rejection email sent to {user.email}"

    except User.DoesNotExist:
        return f"User {doctor_user_id} not found"
    except Exception as exc:
        self.retry(exc=exc, countdown=60)


@shared_task
def send_license_expiry_reminders():
    """
    Celery Beat task: email doctors whose license or malpractice insurance
    expires in 30, 60, or 90 days. Runs daily.
    """
    from datetime import date, timedelta
    from django.core.mail import send_mail
    from apps.accounts.models import DoctorProfile

    today = date.today()
    warning_days = [30, 60, 90]
    notified = 0

    for days in warning_days:
        target = today + timedelta(days=days)

        # License expiry
        for dp in DoctorProfile.objects.filter(
            license_expiry_date=target,
            verification_status='verified',
        ).select_related('user'):
            send_mail(
                subject=f'[MedConsult] Medical License Expires in {days} Days',
                message=(
                    f'Dear Dr. {dp.user.get_display_name()},\n\n'
                    f'Your medical license is due to expire on {target.strftime("%B %d, %Y")} '
                    f'({days} days from today).\n\n'
                    'Please update your license document in your MedConsult profile to avoid '
                    'your account being suspended.\n\nMedConsult Team'
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[dp.user.email],
                fail_silently=True,
            )
            notified += 1

        # Malpractice insurance expiry
        for dp in DoctorProfile.objects.filter(
            malpractice_insurance_expiry=target,
            verification_status='verified',
        ).select_related('user'):
            send_mail(
                subject=f'[MedConsult] Malpractice Insurance Expires in {days} Days',
                message=(
                    f'Dear Dr. {dp.user.get_display_name()},\n\n'
                    f'Your malpractice insurance expires on {target.strftime("%B %d, %Y")} '
                    f'({days} days from today).\n\n'
                    'Please update your insurance information in your MedConsult profile.\n\n'
                    'MedConsult Team'
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[dp.user.email],
                fail_silently=True,
            )
            notified += 1

    return f"License/insurance expiry reminders sent: {notified}"
