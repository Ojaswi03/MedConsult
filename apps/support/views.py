from django.shortcuts import render
from django.contrib import messages
from django.db import transaction

from .models import FAQ, ContactMessage


def help_page(request):
    return render(request, 'support/help.html')


@transaction.atomic
def contact_page(request):
    if request.method == 'POST':
        from .tasks import send_contact_notification_task

        subject = request.POST.get('subject', '').strip()
        message_body = request.POST.get('message', '').strip()
        email = request.POST.get('email', '').strip()
        name = request.POST.get('name', '').strip()

        if not subject or not message_body:
            messages.error(request, 'Subject and message are required.')
            return render(request, 'support/contact.html', {
                'form_data': request.POST,
            })

        # Auto-fill email/name from authenticated user
        if request.user.is_authenticated:
            email = email or request.user.email
            name = name or request.user.get_display_name()

        if not email:
            messages.error(request, 'Please provide your email address.')
            return render(request, 'support/contact.html', {
                'form_data': request.POST,
            })

        contact = ContactMessage.objects.create(
            name=name,
            email=email,
            subject=subject,
            message=message_body,
            user=request.user if request.user.is_authenticated else None,
        )

        send_contact_notification_task.delay(contact.id)

        messages.success(request, 'Your message has been sent. We will get back to you within 1–2 business days.')
        return render(request, 'support/contact.html')

    return render(request, 'support/contact.html')


def faq_page(request):
    faqs = FAQ.objects.filter(is_active=True)
    return render(request, 'support/faq.html', {'faqs': faqs})


def privacy_policy(request):
    return render(request, 'support/privacy_policy.html')


def terms_of_service(request):
    return render(request, 'support/terms_of_service.html')
