from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('accounts', '0020_backfill_organization'),
        ('scheduling', '0020_add_organization_fk'),
    ]

    operations = [
        migrations.AlterField(
            model_name='availabilitywindow',
            name='organization',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='availability_windows',
                to='accounts.organization',
            ),
        ),
        migrations.AlterField(
            model_name='slot',
            name='organization',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='slots',
                to='accounts.organization',
            ),
        ),
        migrations.AlterField(
            model_name='appointment',
            name='organization',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='appointments',
                to='accounts.organization',
            ),
        ),
        migrations.AlterField(
            model_name='waitlistentry',
            name='organization',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='waitlist_entries',
                to='accounts.organization',
            ),
        ),
        migrations.AlterField(
            model_name='referral',
            name='organization',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='referrals',
                to='accounts.organization',
            ),
        ),
        migrations.AlterField(
            model_name='prescription',
            name='organization',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='prescriptions',
                to='accounts.organization',
            ),
        ),
    ]
