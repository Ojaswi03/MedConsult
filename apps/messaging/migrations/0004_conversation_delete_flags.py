from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('messaging', '0003_conversation_direct'),
    ]

    operations = [
        migrations.AddField(
            model_name='conversation',
            name='deleted_by_patient',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='conversation',
            name='deleted_by_doctor',
            field=models.BooleanField(default=False),
        ),
    ]
