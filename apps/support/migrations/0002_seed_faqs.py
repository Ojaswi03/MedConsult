from django.db import migrations


INITIAL_FAQS = [
    {
        'question': 'How do I book an appointment?',
        'answer': 'Navigate to "Find Doctors", select a doctor, choose an available time slot, and confirm your booking. You can filter doctors by specialization, rating, price, and availability.',
        'order': 1,
    },
    {
        'question': 'Can I cancel or reschedule my appointment?',
        'answer': 'Yes. Go to "My Appointments" and select Cancel or Reschedule for any upcoming appointment. Cancellations free the slot for other patients.',
        'order': 2,
    },
    {
        'question': 'How do I become a verified doctor on MedConsult?',
        'answer': 'Sign up as a doctor and complete the 6-step registration including your medical license and government ID. Our admin team will review your documents and notify you by email once verified.',
        'order': 3,
    },
    {
        'question': 'What appointment types are available?',
        'answer': 'Doctors offer Video, Chat, and Phone consultations. Each type may have different pricing and duration. You can see which types a doctor offers on their profile.',
        'order': 4,
    },
    {
        'question': 'How do video consultations work?',
        'answer': 'Once your appointment is confirmed, join the waiting room a few minutes before the start time. Your doctor will admit you when ready. Video uses Daily.co - no download required, works in your browser.',
        'order': 5,
    },
    {
        'question': 'Can I message my doctor outside of a video call?',
        'answer': 'Yes. You can start an in-app chat directly from an appointment or from a doctor\'s profile. Direct messages are not linked to an appointment and responses may be delayed.',
        'order': 6,
    },
    {
        'question': 'How do I download my prescription?',
        'answer': 'After a completed appointment, your doctor may write a digital prescription. Go to "My Appointments", find the appointment, and click "Download Prescription" to get a PDF.',
        'order': 7,
    },
    {
        'question': 'What is the waitlist feature?',
        'answer': 'If a doctor has no available slots, you can join their waitlist. You will be automatically notified when a slot opens up.',
        'order': 8,
    },
]


def seed_faqs(apps, schema_editor):
    FAQ = apps.get_model('support', 'FAQ')
    for faq_data in INITIAL_FAQS:
        FAQ.objects.get_or_create(
            question=faq_data['question'],
            defaults={
                'answer': faq_data['answer'],
                'order': faq_data['order'],
                'is_active': True,
            }
        )


def unseed_faqs(apps, schema_editor):
    FAQ = apps.get_model('support', 'FAQ')
    FAQ.objects.filter(question__in=[f['question'] for f in INITIAL_FAQS]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('support', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_faqs, unseed_faqs),
    ]
