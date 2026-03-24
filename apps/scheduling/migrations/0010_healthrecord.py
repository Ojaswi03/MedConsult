from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('accounts', '0008_doctorprofile_languages'),
        ('scheduling', '0009_waitlistentry'),
    ]
    operations = [
        migrations.CreateModel(
            name='HealthRecord',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('record_type', models.CharField(
                    choices=[
                        ('lab_result', 'Lab Result'),
                        ('imaging', 'Imaging / X-Ray'),
                        ('prescription', 'Prior Prescription'),
                        ('vaccination', 'Vaccination Record'),
                        ('discharge_summary', 'Discharge Summary'),
                        ('other', 'Other'),
                    ],
                    max_length=50
                )),
                ('title', models.CharField(max_length=200)),
                ('description', models.TextField(blank=True)),
                ('file', models.FileField(blank=True, null=True, upload_to='health_records/')),
                ('date_of_record', models.DateField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('patient', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='health_records',
                    to=settings.AUTH_USER_MODEL
                )),
                ('shared_with_doctors', models.ManyToManyField(
                    blank=True,
                    related_name='shared_health_records',
                    to='accounts.doctorprofile'
                )),
            ],
            options={'db_table': 'health_records', 'ordering': ['-created_at']},
        ),
    ]
