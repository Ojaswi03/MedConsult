from django.shortcuts import render
from django.contrib import messages


def help_page(request):
    """Help documentation page."""
    return render(request, 'support/help.html')


def contact_page(request):
    """Contact form page."""
    if request.method == 'POST':
        # TODO: Implement contact form logic
        messages.success(request, 'Your message has been sent. We will get back to you soon.')

    return render(request, 'support/contact.html')


def faq_page(request):
    """FAQ page."""
    faqs = [
        {
            'question': 'How do I book an appointment?',
            'answer': 'Navigate to the "Find Doctors" page, select a doctor, choose an available time slot, and confirm your booking.'
        },
        {
            'question': 'Can I cancel my appointment?',
            'answer': 'Yes, you can cancel your appointment from the "My Appointments" page as long as it hasn\'t started yet.'
        },
        {
            'question': 'How do I become a verified doctor?',
            'answer': 'Sign up as a doctor, complete your profile with your medical license information, and wait for admin verification.'
        },
        {
            'question': 'What if I need to reschedule?',
            'answer': 'You can cancel your current appointment and book a new time slot that works for you.'
        },
    ]

    return render(request, 'support/faq.html', {'faqs': faqs})
