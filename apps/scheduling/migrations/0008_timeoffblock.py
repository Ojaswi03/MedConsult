from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('accounts', '0008_doctorprofile_languages'),
        ('scheduling', '0007_prescription'),
    ]
    operations = [
        migrations.CreateModel(
            name='TimeOffBlock',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('start_date', models.DateField()),
                ('end_date', models.DateField()),
                ('reason', models.CharField(blank=True, max_length=200)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('doctor', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='time_off_blocks',
                    to='accounts.doctorprofile'
                )),
            ],
            options={'db_table': 'time_off_blocks', 'ordering': ['start_date']},
        ),
    ]
