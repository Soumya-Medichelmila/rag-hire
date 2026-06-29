from django.utils import timezone

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from drf_yasg.utils import swagger_auto_schema

from .models import VacancyRequest, JobOpening
from .serializers import VacancyRequestSerializer, JobOpeningSerializer
from accounts.permissions import IsAdminOrHR


# ─────────────────────────────────────────
# VACANCY REQUESTS
# ─────────────────────────────────────────

class VacancyRequestListCreateView(APIView):
    """
    GET  → Admin/HR sees all requests
    POST → Any employee raises a vacancy request
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role and request.user.role.code in ['ADMIN', 'HR']:
            requests = VacancyRequest.objects.all().order_by('-created_at')
        else:
            requests = VacancyRequest.objects.filter(
                requested_by=request.user
            ).order_by('-created_at')
        serializer = VacancyRequestSerializer(requests, many=True)
        return Response(serializer.data)

    @swagger_auto_schema(request_body=VacancyRequestSerializer)
    def post(self, request):
        serializer = VacancyRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(requested_by=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class VacancyRequestAcceptView(APIView):
    """Admin/HR accepts a vacancy request → Auto creates a Job Opening"""
    permission_classes = [IsAuthenticated, IsAdminOrHR]

    def patch(self, request, pk):
        try:
            vacancy = VacancyRequest.objects.get(pk=pk)
        except VacancyRequest.DoesNotExist:
            return Response({'message': 'Vacancy request not found'}, status=status.HTTP_404_NOT_FOUND)

        if vacancy.status != 'PENDING':
            return Response({'message': f'Request is already {vacancy.status}'}, status=status.HTTP_400_BAD_REQUEST)

        vacancy.status = 'ACCEPTED'
        vacancy.reviewed_by = request.user
        vacancy.reviewed_at = timezone.now()
        vacancy.save()

        job = JobOpening.objects.create(
            vacancy_request=vacancy,
            title=vacancy.title,
            department=vacancy.department,
            location=vacancy.location,
            vacancies=vacancy.vacancies,
            experience=vacancy.experience,
            description=vacancy.description,
            posted_by=request.user,
            status='OPEN'
        )
        job.skills.set(vacancy.skills.all())
        job.save()

        return Response({
            'message': 'Vacancy request accepted and job opening created',
            'job_opening_id': job.id
        })


class VacancyRequestRejectView(APIView):
    """Admin/HR rejects a vacancy request with a reason"""
    permission_classes = [IsAuthenticated, IsAdminOrHR]

    def patch(self, request, pk):
        try:
            vacancy = VacancyRequest.objects.get(pk=pk)
        except VacancyRequest.DoesNotExist:
            return Response({'message': 'Vacancy request not found'}, status=status.HTTP_404_NOT_FOUND)

        if vacancy.status != 'PENDING':
            return Response({'message': f'Request is already {vacancy.status}'}, status=status.HTTP_400_BAD_REQUEST)

        rejection_reason = request.data.get('rejection_reason', '')
        if not rejection_reason:
            return Response({'message': 'Rejection reason is required'}, status=status.HTTP_400_BAD_REQUEST)

        vacancy.status = 'REJECTED'
        vacancy.rejection_reason = rejection_reason
        vacancy.reviewed_by = request.user
        vacancy.reviewed_at = timezone.now()
        vacancy.save()

        return Response({'message': 'Vacancy request rejected'})


# ─────────────────────────────────────────
# JOB OPENINGS
# ─────────────────────────────────────────

class JobOpeningListView(APIView):
    """Everyone sees job openings. Admin/HR sees all; employees see OPEN only."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role and request.user.role.code in ['ADMIN', 'HR']:
            jobs = JobOpening.objects.all().order_by('-posted_at')
        else:
            jobs = JobOpening.objects.filter(status='OPEN').order_by('-posted_at')
        serializer = JobOpeningSerializer(jobs, many=True)
        return Response(serializer.data)


class JobOpeningEditView(APIView):
    """
    Admin/HR edits a job opening.
    Basic: title, experience, vacancies, skills
    Structured JD: description, role_summary, responsibilities,
                   required_skills_desc, preferred_skills, technologies
    """
    permission_classes = [IsAuthenticated, IsAdminOrHR]

    def patch(self, request, pk):
        try:
            job = JobOpening.objects.get(pk=pk)
        except JobOpening.DoesNotExist:
            return Response({'message': 'Job opening not found'}, status=status.HTTP_404_NOT_FOUND)

        updatable_fields = [
            'title', 'experience', 'vacancies', 'description',
            'role_summary', 'responsibilities',
            'required_skills_desc', 'preferred_skills', 'technologies',
        ]
        for field in updatable_fields:
            if field in request.data:
                setattr(job, field, request.data[field])
        job.save()

        if 'skills' in request.data:
            job.skills.set(request.data['skills'])

        serializer = JobOpeningSerializer(job)
        return Response(serializer.data)


class JobOpeningCloseView(APIView):
    """Admin/HR closes a job opening when position is filled"""
    permission_classes = [IsAuthenticated, IsAdminOrHR]

    def patch(self, request, pk):
        try:
            job = JobOpening.objects.get(pk=pk)
        except JobOpening.DoesNotExist:
            return Response({'message': 'Job opening not found'}, status=status.HTTP_404_NOT_FOUND)

        if job.status == 'CLOSED':
            return Response({'message': 'Job is already closed'}, status=status.HTTP_400_BAD_REQUEST)

        job.status = 'CLOSED'
        job.closed_at = timezone.now()
        job.save()

        return Response({'message': 'Job opening closed successfully'})