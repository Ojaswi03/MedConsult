from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('messaging', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='message',
            name='attachment',
            field=models.FileField(blank=True, help_text='Optional file attachment', null=True, upload_to='message_attachments/'),
        ),
        migrations.AddField(
            model_name='message',
            name='attachment_name',
            field=models.CharField(blank=True, default='', help_text='Original filename for display', max_length=255),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='message',
            name='message_type',
            field=models.CharField(
                choices=[('text', 'Text'), ('system', 'System'), ('file', 'File Attachment')],
                default='text',
                max_length=10,
            ),
        ),
    ]
