from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("cohorts", "0001_initial"),
        ("enrollments", "0001_initial"),
        ("courses", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="LessonUnlock",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("unlocked_at", models.DateTimeField(auto_now_add=True)),
                (
                    "enrollment",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="lesson_unlocks",
                        to="enrollments.enrollment",
                    ),
                ),
                (
                    "lesson",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="lesson_unlocks",
                        to="courses.lesson",
                    ),
                ),
                (
                    "drip_schedule",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="lesson_unlocks",
                        to="cohorts.dripschedule",
                    ),
                ),
            ],
            options={
                "verbose_name": "Lesson Unlock",
                "verbose_name_plural": "Lesson Unlocks",
                "unique_together": {("enrollment", "lesson")},
            },
        ),
        migrations.AddIndex(
            model_name="lessonunlock",
            index=models.Index(fields=["enrollment", "lesson"], name="cohorts_les_enrollm_idx"),
        ),
    ]
