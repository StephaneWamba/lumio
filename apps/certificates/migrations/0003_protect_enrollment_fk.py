from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('certificates', '0002_earnedcertificate_pdf_s3_key'),
        ('enrollments', '0002_protect_fks'),
    ]

    operations = [
        migrations.AlterField(
            model_name='earnedcertificate',
            name='enrollment',
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='earned_certificate',
                to='enrollments.enrollment',
            ),
        ),
    ]
