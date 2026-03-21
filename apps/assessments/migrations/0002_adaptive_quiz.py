# Migration: add concept_tags to Question, add AttemptConceptScore, EnrollmentConceptProfile
import django.contrib.postgres.fields
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("assessments", "0001_initial"),
        ("enrollments", "0001_initial"),
    ]

    operations = [
        # Add concept_tags to Question
        migrations.AddField(
            model_name="question",
            name="concept_tags",
            field=django.contrib.postgres.fields.ArrayField(
                base_field=models.CharField(max_length=100),
                blank=True,
                default=list,
                help_text="Concept tags for adaptive question selection (e.g. ['algebra', 'fractions'])",
                size=None,
            ),
        ),
        # AttemptConceptScore
        migrations.CreateModel(
            name="AttemptConceptScore",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("concept", models.CharField(max_length=100)),
                (
                    "score_pct",
                    models.DecimalField(
                        decimal_places=2,
                        max_digits=5,
                        help_text="Score percentage for this concept in this attempt (0–100)",
                    ),
                ),
                (
                    "attempt",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="concept_scores",
                        to="assessments.quizattempt",
                    ),
                ),
            ],
            options={
                "verbose_name": "Attempt Concept Score",
                "verbose_name_plural": "Attempt Concept Scores",
                "unique_together": {("attempt", "concept")},
            },
        ),
        # EnrollmentConceptProfile
        migrations.CreateModel(
            name="EnrollmentConceptProfile",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("concept", models.CharField(db_index=True, max_length=100)),
                (
                    "avg_score",
                    models.DecimalField(
                        decimal_places=2,
                        max_digits=5,
                        help_text="Running average score percentage for this concept (0–100)",
                    ),
                ),
                (
                    "sample_count",
                    models.PositiveIntegerField(
                        default=1,
                        help_text="Number of attempts factored into avg_score",
                    ),
                ),
                (
                    "enrollment",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="concept_profiles",
                        to="enrollments.enrollment",
                    ),
                ),
            ],
            options={
                "verbose_name": "Enrollment Concept Profile",
                "verbose_name_plural": "Enrollment Concept Profiles",
                "unique_together": {("enrollment", "concept")},
            },
        ),
        migrations.AddIndex(
            model_name="enrollmentconceptprofile",
            index=models.Index(
                fields=["enrollment", "avg_score"],
                name="assessments_enroll_concept_idx",
            ),
        ),
    ]
