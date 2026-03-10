# Generated migration for notifications app
from django.db import migrations, models
import django.db.models.deletion
import django.contrib.postgres.fields


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('users', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='NotificationTemplate',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('trigger', models.CharField(choices=[('course_published', 'Course Published'), ('enrollment_confirmed', 'Enrollment Confirmed'), ('lesson_available', 'Lesson Available'), ('drip_content_released', 'Drip Content Released'), ('quiz_available', 'Quiz Available'), ('quiz_graded', 'Quiz Graded'), ('certificate_earned', 'Certificate Earned'), ('instructor_announcement', 'Instructor Announcement')], max_length=50, unique=True)),
                ('name', models.CharField(max_length=255)),
                ('subject', models.CharField(help_text='Email subject with optional placeholders', max_length=255)),
                ('message', models.TextField(help_text='Notification message with optional placeholders: {user_name}, {course_title}, etc.')),
                ('send_in_app', models.BooleanField(default=True)),
                ('send_email', models.BooleanField(default=True)),
                ('send_push', models.BooleanField(default=False)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Notification Template',
                'verbose_name_plural': 'Notification Templates',
                'ordering': ['trigger'],
            },
        ),
        migrations.CreateModel(
            name='NotificationPreference',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('enable_in_app', models.BooleanField(default=True)),
                ('enable_email', models.BooleanField(default=True)),
                ('enable_push', models.BooleanField(default=False)),
                ('email_digest_frequency', models.CharField(choices=[('immediate', 'Immediate'), ('daily', 'Daily'), ('weekly', 'Weekly'), ('never', 'Never')], default='daily', max_length=20)),
                ('enabled_categories', django.contrib.postgres.fields.ArrayField(base_field=models.CharField(max_length=50), default=list, help_text='List of trigger types to receive notifications for', size=None)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='notification_preferences', to='users.user')),
            ],
            options={
                'verbose_name': 'Notification Preference',
                'verbose_name_plural': 'Notification Preferences',
            },
        ),
        migrations.CreateModel(
            name='Notification',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('notification_type', models.CharField(choices=[('info', 'Info'), ('success', 'Success'), ('warning', 'Warning'), ('error', 'Error')], default='info', max_length=20)),
                ('subject', models.CharField(max_length=255)),
                ('message', models.TextField()),
                ('action_url', models.URLField(blank=True, help_text='Link to action related to notification')),
                ('is_read', models.BooleanField(default=False)),
                ('read_at', models.DateTimeField(blank=True, null=True)),
                ('email_sent', models.BooleanField(default=False)),
                ('email_sent_at', models.DateTimeField(blank=True, null=True)),
                ('push_sent', models.BooleanField(default=False)),
                ('push_sent_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('template', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='notifications', to='notifications.notificationtemplate')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='notifications', to='users.user')),
            ],
            options={
                'verbose_name': 'Notification',
                'verbose_name_plural': 'Notifications',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='NotificationLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('log_type', models.CharField(choices=[('created', 'Created'), ('email_sent', 'Email Sent'), ('email_failed', 'Email Failed'), ('push_sent', 'Push Sent'), ('push_failed', 'Push Failed'), ('read', 'Read')], max_length=20)),
                ('details', models.TextField(blank=True, help_text='JSON details of the log entry')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('notification', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='logs', to='notifications.notification')),
            ],
            options={
                'verbose_name': 'Notification Log',
                'verbose_name_plural': 'Notification Logs',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='notification',
            index=models.Index(fields=['user', '-created_at'], name='notification_user_created_idx'),
        ),
        migrations.AddIndex(
            model_name='notification',
            index=models.Index(fields=['is_read', '-created_at'], name='notification_read_idx'),
        ),
        migrations.AddIndex(
            model_name='notificationlog',
            index=models.Index(fields=['notification', '-created_at'], name='notif_log_notif_idx'),
        ),
        migrations.AddIndex(
            model_name='notificationlog',
            index=models.Index(fields=['log_type', '-created_at'], name='notif_log_type_idx'),
        ),
    ]
