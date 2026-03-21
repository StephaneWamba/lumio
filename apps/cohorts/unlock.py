"""Shared helper: create LessonUnlock records when a DripSchedule is released."""

from .models import DripSchedule, LessonUnlock


def create_lesson_unlocks_for_schedule(schedule: DripSchedule) -> int:
    """
    Bulk-create LessonUnlock rows for every active cohort member.

    Returns the number of new unlock records created.
    If drip_type is 'lesson', unlock that one lesson.
    If drip_type is 'section', unlock every lesson in the section.
    Skips members who already have an unlock for the same (enrollment, lesson) pair.
    """
    from apps.enrollments.models import Enrollment

    # Determine which lessons to unlock
    if schedule.drip_type == DripSchedule.DRIP_TYPE_LESSON:
        lessons = [schedule.lesson] if schedule.lesson else []
    else:  # section
        lessons = list(schedule.section.lessons.all()) if schedule.section else []

    if not lessons:
        return 0

    # Collect active cohort member enrollments
    active_members = schedule.cohort.members.filter(is_active=True).select_related("enrollment")

    unlocks = []
    for member in active_members:
        enrollment = member.enrollment
        for lesson in lessons:
            unlocks.append(
                LessonUnlock(
                    enrollment=enrollment,
                    lesson=lesson,
                    drip_schedule=schedule,
                )
            )

    created = LessonUnlock.objects.bulk_create(unlocks, ignore_conflicts=True)
    return len(created)
