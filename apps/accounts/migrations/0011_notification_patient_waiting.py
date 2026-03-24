from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0010_patientprofile_preferred_language'),
    ]

    operations = [
        migrations.AlterField(
            model_name='notification',
            name='notif_type',
            field=models.CharField(
                choices=[
                    ('appointment_booked', 'Appointment Booked'),
                    ('appointment_cancelled', 'Appointment Cancelled'),
                    ('appointment_reminder', 'Appointment Reminder'),
                    ('appointment_rescheduled', 'Appointment Rescheduled'),
                    ('doctor_verified', 'Doctor Verified'),
                    ('doctor_rejected', 'Doctor Rejected'),
                    ('new_review', 'New Review'),
                    ('prescription_ready', 'Prescription Ready'),
                    ('waitlist_slot_available', 'Slot Available'),
                    ('referral_received', 'Referral Received'),
                    ('health_record_shared', 'Health Record Shared'),
                    ('patient_waiting', 'Patient in Waiting Room'),
                ],
                max_length=50,
            ),
        ),
    ]
