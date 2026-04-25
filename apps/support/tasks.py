from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings


@shared_task(bind=True, max_retries=3)
def send_contact_notification_task(self, contact_id):
    """Notify admins of a new contact form submission."""
    from .models import ContactMessage

    try:
        contact = ContactMessage.objects.get(id=contact_id)

        subject = f'[MedConsult Support] New message: {contact.subject}'
        message = (
            f'New contact message received.\n\n'
            f'From: {contact.name or "Anonymous"} <{contact.email}>\n'
            f'Subject: {contact.subject}\n\n'
            f'Message:\n{contact.message}\n\n'
            f'Submitted: {contact.created_at.strftime("%Y-%m-%d %H:%M UTC")}\n'
            f'View in admin: /admin/support/contactmessage/{contact.id}/change/'
        )

        admin_email = getattr(settings, 'SUPPORT_EMAIL', settings.DEFAULT_FROM_EMAIL)

        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[admin_email],
            fail_silently=False,
        )

        return f'Contact notification sent for message {contact_id}'

    except ContactMessage.DoesNotExist:
        return f'ContactMessage {contact_id} not found'
    except Exception as exc:
        self.retry(exc=exc, countdown=60)
