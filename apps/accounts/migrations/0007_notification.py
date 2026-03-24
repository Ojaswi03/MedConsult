from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('accounts', '0006_user_profile_image'),
    ]
    operations = [
        migrations.CreateModel(
            name='Notification',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('notif_type', models.CharField(choices=[
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
                ], max_length=50)),
                ('title', models.CharField(max_length=200)),
                ('message', models.TextField()),
                ('link', models.CharField(blank=True, max_length=500)),
                ('is_read', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='notifications',
                    to=settings.AUTH_USER_MODEL
                )),
            ],
            options={'db_table': 'notifications', 'ordering': ['-created_at']},
        ),
        migrations.AddIndex(
            model_name='notification',
            index=models.Index(fields=['user', 'is_read', 'created_at'], name='notif_user_read_idx'),
        ),
    ]
