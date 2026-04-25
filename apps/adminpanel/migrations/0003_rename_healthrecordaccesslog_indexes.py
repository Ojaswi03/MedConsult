from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('adminpanel', '0002_healthrecordaccesslog_extend_actiontypes'),
    ]

    operations = [
        migrations.RenameIndex(
            model_name='healthrecordaccesslog',
            new_name='health_reco_record__655ee5_idx',
            old_name='health_rec_record__idx',
        ),
        migrations.RenameIndex(
            model_name='healthrecordaccesslog',
            new_name='health_reco_accesse_3aa7c9_idx',
            old_name='health_rec_accessed_idx',
        ),
    ]
