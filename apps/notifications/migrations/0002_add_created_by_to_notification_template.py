from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('notifications', '0001_initial'),
        ('users', '0001_initial'),
    ]

    operations = [
        # Drop the unique constraint on trigger so multiple instructors
        # can each have a template for the same trigger type.
        migrations.AlterField(
            model_name='notificationtemplate',
            name='trigger',
            field=models.CharField(
                choices=[
                    ('course_published', 'Course Published'),
                    ('enrollment_confirmed', 'Enrollment Confirmed'),
                    ('lesson_available', 'Lesson Available'),
                    ('drip_content_released', 'Drip Content Released'),
                    ('quiz_available', 'Quiz Available'),
                    ('quiz_graded', 'Quiz Graded'),
                    ('certificate_earned', 'Certificate Earned'),
                    ('instructor_announcement', 'Instructor Announcement'),
                ],
                max_length=50,
            ),
        ),
        migrations.AddField(
            model_name='notificationtemplate',
            name='created_by',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='notification_templates',
                to='users.user',
            ),
        ),
    ]
