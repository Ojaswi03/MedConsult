from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('accounts', '0007_notification'),
    ]
    operations = [
        migrations.AddField(
            model_name='doctorprofile',
            name='languages',
            field=models.CharField(
                blank=True,
                help_text='Comma-separated languages spoken (e.g., English, Spanish)',
                max_length=200
            ),
        ),
    ]
