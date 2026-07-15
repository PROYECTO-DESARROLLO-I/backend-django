# Generated manually for HU04 internal staff account creation

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("administrative", "0002_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="administrative",
            name="identity_document",
            field=models.CharField(
                blank=True,
                db_column="documento_identidad",
                max_length=50,
                null=True,
                unique=True,
            ),
        ),
    ]
