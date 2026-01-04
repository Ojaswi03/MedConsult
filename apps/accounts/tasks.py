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
