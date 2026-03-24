from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('scheduling', '0011_referral'),
    ]

    operations = [
        migrations.AddField(
            model_name='appointment',
            name='cpt_code',
            field=models.CharField(blank=True, default='', help_text='CPT billing code for insurance claims', max_length=20),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='appointment',
            name='is_second_opinion',
            field=models.BooleanField(default=False, help_text='Whether this appointment is a second opinion request'),
        ),
    ]
