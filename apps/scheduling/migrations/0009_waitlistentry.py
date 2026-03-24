from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('accounts', '0008_doctorprofile_languages'),
        ('scheduling', '0008_timeoffblock'),
    ]
    operations = [
        migrations.CreateModel(
            name='WaitlistEntry',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('appointment_type', models.CharField(
                    blank=True,
                    choices=[
                        ('video', 'Video Consultation'),
                        ('chat', 'Chat Consultation'),
                        ('phone', 'Phone Consultation'),
                    ],
                    max_length=20
                )),
                ('preferred_date', models.DateField(blank=True, null=True)),
                ('notes', models.TextField(blank=True)),
                ('is_notified', models.BooleanField(default=False)),
                ('notified_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('doctor', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='waitlist_entries',
                    to='accounts.doctorprofile'
                )),
                ('patient', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='waitlist_entries',
                    to=settings.AUTH_USER_MODEL
                )),
            ],
            options={
                'db_table': 'waitlist_entries',
                'ordering': ['created_at'],
                'unique_together': {('doctor', 'patient')},
            },
        ),
    ]
