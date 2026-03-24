import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('adminpanel', '0001_initial'),
        ('scheduling', '0014_availabilityexception'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name='adminactivitylog',
            name='action_type',
            field=models.CharField(
                choices=[
                    ('doctor_verified', 'Doctor Verified'),
                    ('doctor_rejected', 'Doctor Rejected'),
                    ('user_activated', 'User Activated'),
                    ('user_deactivated', 'User Deactivated'),
                    ('user_viewed', 'User Viewed'),
                    ('document_viewed', 'Document Viewed'),
                    ('export_created', 'Export Created'),
                    ('settings_changed', 'Settings Changed'),
                    ('bulk_verify', 'Bulk Doctor Verify'),
                    ('bulk_reject', 'Bulk Doctor Reject'),
                    ('slot_created', 'Slot Created'),
                    ('slot_blocked', 'Slot Blocked'),
                    ('slot_unblocked', 'Slot Unblocked'),
                    ('slot_deleted', 'Slot Deleted'),
                    ('appointment_cancelled', 'Appointment Cancelled'),
                    ('refund_processed', 'Refund Processed'),
                ],
                max_length=50,
            ),
        ),
        migrations.CreateModel(
            name='HealthRecordAccessLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('access_type', models.CharField(choices=[('viewed', 'Viewed'), ('downloaded', 'Downloaded'), ('shared', 'Shared'), ('unshared', 'Unshared')], max_length=20)),
                ('ip_address', models.GenericIPAddressField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('accessed_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='health_record_access_logs', to=settings.AUTH_USER_MODEL)),
                ('record', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='access_logs', to='scheduling.healthrecord')),
            ],
            options={
                'db_table': 'health_record_access_logs',
                'ordering': ['-created_at'],
                'indexes': [
                    models.Index(fields=['record', 'created_at'], name='health_rec_record__idx'),
                    models.Index(fields=['accessed_by', 'created_at'], name='health_rec_accessed_idx'),
                ],
            },
        ),
    ]
