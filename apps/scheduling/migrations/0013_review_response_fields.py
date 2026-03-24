from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('scheduling', '0012_appointment_cpt_is_second_opinion'),
    ]

    operations = [
        migrations.AddField(
            model_name='review',
            name='response_text',
            field=models.TextField(blank=True, default='', help_text='Doctor response to this review'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='review',
            name='responded_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
