from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('accounts', '0020_backfill_organization'),
        ('messaging', '0005_add_organization_fk'),
    ]

    operations = [
        migrations.AlterField(
            model_name='conversation',
            name='organization',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='conversations',
                to='accounts.organization',
            ),
        ),
    ]
