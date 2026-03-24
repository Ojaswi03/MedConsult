from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0009_doctorprofile_npi_second_opinions'),
    ]

    operations = [
        migrations.AddField(
            model_name='patientprofile',
            name='preferred_language',
            field=models.CharField(blank=True, default='', help_text='Patient preferred language for consultations', max_length=50),
            preserve_default=False,
        ),
    ]
