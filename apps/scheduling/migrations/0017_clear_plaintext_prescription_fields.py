from django.db import migrations


def clear_plaintext_prescription_fields(apps, schema_editor):
    """NULL out prescription encrypted fields that contain pre-encryption plaintext."""
    db = schema_editor.connection
    with db.cursor() as c:
        c.execute("""
            UPDATE prescriptions
            SET
                diagnosis = NULL,
                medications = NULL,
                instructions = NULL,
                notes = NULL
            WHERE
                medications IS NOT NULL
                AND (
                    octet_length(medications) < 100
                    OR substring(medications::text FROM 1 FOR 6) != 'gAAAAA'
                )
        """)


class Migration(migrations.Migration):

    dependencies = [
        ('scheduling', '0016_alter_prescription_diagnosis_and_more'),
    ]

    operations = [
        migrations.RunPython(clear_plaintext_prescription_fields, migrations.RunPython.noop),
    ]
