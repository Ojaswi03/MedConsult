from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0008_doctorprofile_languages'),
    ]

    operations = [
        migrations.AddField(
            model_name='doctorprofile',
            name='npi_number',
            field=models.CharField(blank=True, default='', help_text='National Provider Identifier (10-digit NPI)', max_length=20),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='doctorprofile',
            name='offers_second_opinions',
            field=models.BooleanField(default=False, help_text='Whether doctor offers second opinion consultations'),
        ),
    ]
