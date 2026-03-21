from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("certificates", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="earnedcertificate",
            name="pdf_s3_key",
            field=models.CharField(
                blank=True,
                null=True,
                max_length=500,
                help_text="S3 key for the rendered PDF in the assets bucket",
            ),
        ),
    ]
