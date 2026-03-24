from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
from datetime import timedelta


class Migration(migrations.Migration):
    dependencies = [
        ('accounts', '0008_doctorprofile_languages'),
        ('scheduling', '0010_healthrecord'),
    ]
    operations = [
        migrations.CreateModel(
            name='Referral',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('reason', models.TextField()),
                ('notes', models.TextField(blank=True)),
                ('status', models.CharField(
                    choices=[
                        ('pending', 'Pending'),
                        ('accepted', 'Accepted'),
                        ('booked', 'Booked'),
                        ('expired', 'Expired'),
                    ],
                    default='pending',
                    max_length=20
                )),
                ('expires_at', models.DateTimeField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('referring_doctor', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='referrals_sent',
                    to='accounts.doctorprofile'
                )),
                ('referred_to_doctor', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='referrals_received',
                    to='accounts.doctorprofile'
                )),
                ('patient', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='referrals',
                    to=settings.AUTH_USER_MODEL
                )),
                ('appointment', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='referral',
                    to='scheduling.appointment'
                )),
            ],
            options={'db_table': 'referrals', 'ordering': ['-created_at']},
        ),
    ]
