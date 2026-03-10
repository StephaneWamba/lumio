# Generated migration for certificates app
from django.db import migrations, models
import django.db.models.deletion
import django.core.validators
import django.utils.timezone


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('courses', '0001_initial'),
        ('enrollments', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='CertificateTemplate',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(help_text="Certificate title e.g., 'Certificate of Completion'", max_length=255)),
                ('description', models.TextField(blank=True)),
                ('content', models.TextField(help_text='Certificate body text with optional placeholders: {student_name}, {course_title}, {completion_date}')),
                ('institution_name', models.CharField(blank=True, max_length=255)),
                ('signature_text', models.CharField(blank=True, help_text='Signatory name/title', max_length=255)),
                ('logo_url', models.URLField(blank=True, help_text='URL to institution logo')),
                ('color_primary', models.CharField(default='#003366', help_text='Primary brand color (hex)', max_length=7)),
                ('color_accent', models.CharField(default='#0099CC', help_text='Accent color (hex)', max_length=7)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('course', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='certificate_template', to='courses.course')),
            ],
            options={
                'verbose_name': 'Certificate Template',
                'verbose_name_plural': 'Certificate Templates',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='CertificateAward',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('condition', models.CharField(choices=[('course_completed', 'Course Completed'), ('score_minimum', 'Minimum Score Required'), ('course_completed_with_score', 'Course Completed with Minimum Score')], default='course_completed', max_length=50)),
                ('minimum_score', models.DecimalField(decimal_places=2, default=70, help_text='Minimum percentage score required (0-100)', max_digits=5, validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(100)])),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('course', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='certificate_award', to='courses.course')),
            ],
            options={
                'verbose_name': 'Certificate Award Criteria',
                'verbose_name_plural': 'Certificate Award Criteria',
            },
        ),
        migrations.CreateModel(
            name='EarnedCertificate',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('certificate_number', models.CharField(help_text='Unique identifier for certificate verification', max_length=50, unique=True)),
                ('issued_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('rendered_content', models.TextField(help_text='Final certificate content with placeholders filled in')),
                ('is_revoked', models.BooleanField(default=False)),
                ('revoked_at', models.DateTimeField(blank=True, null=True)),
                ('revocation_reason', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('enrollment', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='earned_certificate', to='enrollments.enrollment')),
                ('template', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='earned_certificates', to='certificates.certificatetemplate')),
            ],
            options={
                'verbose_name': 'Earned Certificate',
                'verbose_name_plural': 'Earned Certificates',
                'ordering': ['-issued_at'],
            },
        ),
    ]
