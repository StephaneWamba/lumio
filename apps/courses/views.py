"""Course views"""

from django.shortcuts import get_object_or_404
from rest_framework import viewsets, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticatedOrReadOnly
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination

from apps.users.models import User
from .models import Course, Section, Lesson
from .serializers import (
    CourseListSerializer,
    CourseDetailSerializer,
    CourseCreateUpdateSerializer,
    SectionSerializer,
    LessonSerializer,
)
import structlog

logger = structlog.get_logger()


class CourseListPagination(PageNumberPagination):
    """Pagination for course listings"""

    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class CourseViewSet(viewsets.ModelViewSet):
    """Course CRUD"""

    queryset = Course.objects.all()
    permission_classes = [AllowAny]
    pagination_class = CourseListPagination

    def get_serializer_class(self):
        if self.action == "list":
            return CourseListSerializer
        elif self.action == "retrieve":
            return CourseDetailSerializer
        elif self.action in ["create", "update", "partial_update"]:
            return CourseCreateUpdateSerializer
        return CourseDetailSerializer

    def get_queryset(self):
        """Filter published courses for students, all for instructor"""
        user = self.request.user
        if user and user.is_authenticated and user.role == User.ROLE_INSTRUCTOR:
            return Course.objects.filter(instructor=user)
        return Course.objects.filter(is_published=True)

    def perform_create(self, serializer):
        """Set instructor to current user"""
        if self.request.user.is_anonymous or self.request.user.role != User.ROLE_INSTRUCTOR:
            raise PermissionDenied("Only instructors can create courses")
        serializer.save(instructor=self.request.user)
        logger.info(
            "course_created",
            course_id=serializer.instance.id,
            instructor_id=self.request.user.id,
        )

    def perform_update(self, serializer):
        """Check instructor permission"""
        if serializer.instance.instructor != self.request.user:
            raise PermissionDenied("You can only edit your own courses")
        serializer.save()
        logger.info("course_updated", course_id=serializer.instance.id)

    @action(detail=True, methods=["get"])
    def publish(self, request, pk=None):
        """Publish a course"""
        course = self.get_object()
        if course.instructor != request.user:
            return Response(
                {"error": "You can only publish your own courses"},
                status=status.HTTP_403_FORBIDDEN,
            )
        course.is_published = True
        course.save()
        logger.info("course_published", course_id=course.id)
        return Response({"message": "Course published"}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["get"])
    def unpublish(self, request, pk=None):
        """Unpublish a course"""
        course = self.get_object()
        if course.instructor != request.user:
            return Response(
                {"error": "You can only unpublish your own courses"},
                status=status.HTTP_403_FORBIDDEN,
            )
        course.is_published = False
        course.save()
        logger.info("course_unpublished", course_id=course.id)
        return Response({"message": "Course unpublished"}, status=status.HTTP_200_OK)


class SectionViewSet(viewsets.ModelViewSet):
    """Section CRUD"""

    serializer_class = SectionSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        """Filter by course"""
        course_id = self.kwargs.get("course_id")
        if course_id:
            return Section.objects.filter(course_id=course_id)
        return Section.objects.none()

    def perform_create(self, serializer):
        """Set course from URL param"""
        course_id = self.kwargs.get("course_id")
        course = get_object_or_404(Course, id=course_id)
        if course.instructor != self.request.user:
            raise PermissionDenied("You can only create sections in your own courses")
        serializer.save(course=course)
        logger.info("section_created", section_id=serializer.instance.id)

    def perform_update(self, serializer):
        """Check instructor permission"""
        if serializer.instance.course.instructor != self.request.user:
            raise PermissionDenied("You can only edit sections in your own courses")
        serializer.save()
        logger.info("section_updated", section_id=serializer.instance.id)


class LessonViewSet(viewsets.ModelViewSet):
    """Lesson CRUD"""

    serializer_class = LessonSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        """Filter by section"""
        section_id = self.kwargs.get("section_id")
        if section_id:
            return Lesson.objects.filter(section_id=section_id)
        return Lesson.objects.none()

    def perform_create(self, serializer):
        """Set section from URL param"""
        section_id = self.kwargs.get("section_id")
        section = get_object_or_404(Section, id=section_id)
        if section.course.instructor != self.request.user:
            raise PermissionDenied("You can only create lessons in your own courses")
        serializer.save(section=section)
        logger.info("lesson_created", lesson_id=serializer.instance.id)

    def perform_update(self, serializer):
        """Check instructor permission"""
        if serializer.instance.section.course.instructor != self.request.user:
            raise PermissionDenied("You can only edit lessons in your own courses")
        serializer.save()
        logger.info("lesson_updated", lesson_id=serializer.instance.id)

    @action(detail=True, methods=["post"])
    def request_video_upload_url(self, request, pk=None, section_id=None):
        """Get presigned S3 URL for video upload (TODO: Phase 3)"""
        # TODO: Generate presigned upload URL via S3
        return Response(
            {"error": "Video upload coming in Phase 3"},
            status=status.HTTP_501_NOT_IMPLEMENTED,
        )
