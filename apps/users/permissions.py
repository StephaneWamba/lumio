"""Custom permission classes for role-based and object-level access control"""
from rest_framework import permissions
from .models import User


class IsStudent(permissions.BasePermission):
    """Allow only students"""

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role == User.ROLE_STUDENT
        )


class IsInstructor(permissions.BasePermission):
    """Allow only approved instructors"""

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role == User.ROLE_INSTRUCTOR
            and hasattr(request.user, "instructor_profile")
            and request.user.instructor_profile.is_approved
        )


class IsAdmin(permissions.BasePermission):
    """Allow only admins"""

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role == User.ROLE_ADMIN
        )


class IsCorporateManager(permissions.BasePermission):
    """Allow only corporate managers"""

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role == User.ROLE_CORPORATE_MANAGER
        )


class IsInstructorOrReadOnly(permissions.BasePermission):
    """Allow instructors to edit, everyone else read-only"""

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return bool(
            request.user
            and request.user.is_authenticated
            and (
                request.user.role == User.ROLE_INSTRUCTOR
                or request.user.is_superuser
            )
        )


class IsContentOwner(permissions.BasePermission):
    """Allow only the owner of the content to edit"""

    def has_object_permission(self, request, view, obj):
        # Safe methods allowed for all
        if request.method in permissions.SAFE_METHODS:
            return True

        # Check if user is the owner
        if hasattr(obj, "instructor"):
            return obj.instructor == request.user
        elif hasattr(obj, "user"):
            return obj.user == request.user
        elif hasattr(obj, "author"):
            return obj.author == request.user

        return False


class IsEnrolledStudent(permissions.BasePermission):
    """Allow only enrolled students to access course content"""

    def has_object_permission(self, request, view, obj):
        """Check if student is enrolled in the course"""
        from apps.enrollments.models import Enrollment

        if not request.user or not request.user.is_authenticated:
            return False

        # Course instructors and admins can always access
        if hasattr(obj, "instructor") and obj.instructor == request.user:
            return True
        if request.user.is_superuser or request.user.is_staff:
            return True

        # Check enrollment
        if hasattr(obj, "id"):  # Course object
            return Enrollment.objects.filter(
                user=request.user,
                course=obj,
                status="active",
            ).exists()

        return False


class CanAccessLesson(permissions.BasePermission):
    """Allow students to access lessons they're enrolled in + no prerequisites"""

    def has_object_permission(self, request, view, obj):
        """Check if student can access this lesson"""
        from apps.enrollments.models import Enrollment, ProgressEvent

        if not request.user or not request.user.is_authenticated:
            return False

        # Course instructors can always access
        if hasattr(obj, "section") and hasattr(obj.section, "course"):
            if obj.section.course.instructor == request.user:
                return True
        if request.user.is_superuser or request.user.is_staff:
            return True

        # Check enrollment in course
        if hasattr(obj, "section") and hasattr(obj.section, "course"):
            enrollment = Enrollment.objects.filter(
                user=request.user,
                course=obj.section.course,
                status="active",
            ).first()

            if not enrollment:
                return False

            # Check prerequisites
            if obj.prerequisite_lesson:
                has_prerequisite = ProgressEvent.objects.filter(
                    enrollment=enrollment,
                    lesson=obj.prerequisite_lesson,
                    event_type="lesson_completed",
                ).exists()
                return has_prerequisite

            return True

        return False


class CanTakeQuiz(permissions.BasePermission):
    """Allow students to take quizzes if they're enrolled and lessons are accessible"""

    def has_object_permission(self, request, view, obj):
        """Check if student can take this quiz"""
        from apps.enrollments.models import Enrollment

        if not request.user or not request.user.is_authenticated:
            return False

        # Instructors can always access their quizzes
        if hasattr(obj, "lesson") and hasattr(obj.lesson, "section"):
            if obj.lesson.section.course.instructor == request.user:
                return True

        if request.user.is_superuser or request.user.is_staff:
            return True

        # Check enrollment
        if hasattr(obj, "lesson") and hasattr(obj.lesson, "section"):
            course = obj.lesson.section.course
            return Enrollment.objects.filter(
                user=request.user,
                course=course,
                status="active",
            ).exists()

        return False
