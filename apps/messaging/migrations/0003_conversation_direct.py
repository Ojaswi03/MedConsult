from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('messaging', '0002_message_attachment'),
        ('scheduling', '0014_availabilityexception'),
    ]

    operations = [
        migrations.AlterField(
            model_name='conversation',
            name='appointment',
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='conversation',
                to='scheduling.appointment',
            ),
        ),
        migrations.AddField(
            model_name='conversation',
            name='is_direct',
            field=models.BooleanField(
                default=False,
                help_text='True when started without a scheduled appointment',
            ),
        ),
    ]
