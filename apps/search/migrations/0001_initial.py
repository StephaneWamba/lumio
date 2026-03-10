"""Initial search app migration"""
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.contrib.postgres.search


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="SearchIndex",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("content_type", models.CharField(
                    choices=[("course", "Course"), ("lesson", "Lesson"), ("instructor", "Instructor")],
                    max_length=20,
                )),
                ("object_id", models.PositiveIntegerField()),
                ("title", models.CharField(max_length=500)),
                ("description", models.TextField(blank=True)),
                ("instructor_name", models.CharField(blank=True, db_index=True, max_length=255)),
                ("category", models.CharField(blank=True, db_index=True, max_length=100)),
                ("difficulty", models.CharField(blank=True, max_length=20)),
                ("duration_hours", models.FloatField(blank=True, null=True)),
                ("rating", models.FloatField(blank=True, null=True)),
                ("review_count", models.PositiveIntegerField(default=0)),
                ("enrollment_count", models.PositiveIntegerField(default=0)),
                ("is_published", models.BooleanField(db_index=True, default=True)),
                ("search_vector", django.contrib.postgres.search.SearchVectorField(db_index=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name_plural": "Search Indexes",
            },
        ),
        migrations.CreateModel(
            name="SearchQuery",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("query", models.CharField(db_index=True, max_length=255)),
                ("result_count", models.PositiveIntegerField(default=0)),
                ("timestamp", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("user", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name_plural": "Search Queries",
            },
        ),
        migrations.AddIndex(
            model_name="searchindex",
            index=models.Index(fields=["content_type", "is_published"], name="search_sear_content_4a1b2c_idx"),
        ),
        migrations.AddIndex(
            model_name="searchindex",
            index=models.Index(fields=["category", "is_published"], name="search_sear_categor_8f3d9e_idx"),
        ),
        migrations.AddIndex(
            model_name="searchindex",
            index=models.Index(fields=["-rating", "review_count"], name="search_sear_rating_7c5f2a_idx"),
        ),
        migrations.AddIndex(
            model_name="searchindex",
            index=models.Index(fields=["-created_at"], name="search_sear_created_9b1e4d_idx"),
        ),
        migrations.AlterUniqueTogether(
            name="searchindex",
            unique_together={("content_type", "object_id")},
        ),
        migrations.AddIndex(
            model_name="searchquery",
            index=models.Index(fields=["-timestamp"], name="search_sear_timesta_5a2c1f_idx"),
        ),
        migrations.AddIndex(
            model_name="searchquery",
            index=models.Index(fields=["query", "-timestamp"], name="search_sear_query_3b7e8d_idx"),
        ),
    ]
