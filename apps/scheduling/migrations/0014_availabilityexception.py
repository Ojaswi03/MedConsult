import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0009_doctorprofile_npi_second_opinions'),
        ('scheduling', '0013_review_response_fields'),
    ]

    operations = [
        migrations.CreateModel(
            name='AvailabilityException',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateField(help_text='The date this exception applies to')),
                ('start_time', models.TimeField(blank=True, help_text='If set, only this time window is available. If null, entire day is blocked.', null=True)),
                ('end_time', models.TimeField(blank=True, null=True)),
                ('reason', models.CharField(blank=True, max_length=200)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('doctor', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='availability_exceptions', to='accounts.doctorprofile')),
            ],
            options={
                'db_table': 'availability_exceptions',
                'ordering': ['date'],
                'unique_together': {('doctor', 'date')},
            },
        ),
    ]
