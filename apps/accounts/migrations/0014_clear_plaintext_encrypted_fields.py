from django.db import migrations


def clear_plaintext_doctor_fields(apps, schema_editor):
    """
    NULL out any encrypted fields that contain pre-encryption plaintext.
    Fernet tokens are base64url and start with 'gAAAAA'. Anything else is stale.
    """
    db = schema_editor.connection
    with db.cursor() as c:
        c.execute("""
            UPDATE doctor_profiles
            SET
                medical_license_number = NULL,
                account_number = NULL,
                routing_number = NULL
            WHERE
                medical_license_number IS NOT NULL
                AND (
                    octet_length(medical_license_number) < 100
                    OR substring(medical_license_number::text FROM 1 FOR 6) != 'gAAAAA'
                )
        """)


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0013_alter_doctorprofile_account_number_and_more'),
    ]

    operations = [
        migrations.RunPython(clear_plaintext_doctor_fields, migrations.RunPython.noop),
    ]
