from rest_framework import serializers
from .models import VacancyRequest, JobOpening
from masters.models import Department, Location, Skill


class VacancyRequestSerializer(serializers.ModelSerializer):

    department_name = serializers.CharField(source='department.name', read_only=True)
    location_name = serializers.CharField(source='location.name', read_only=True, allow_null=True)
    skill_names = serializers.SerializerMethodField()
    requested_by_name = serializers.CharField(source='requested_by.get_full_name', read_only=True)
    reviewed_by_name = serializers.CharField(source='reviewed_by.get_full_name', read_only=True, allow_null=True)

    class Meta:
        model = VacancyRequest
        fields = [
            'id', 'title',
            'department', 'department_name',
            'location', 'location_name',
            'skills', 'skill_names',
            'vacancies', 'experience', 'description',
            'status', 'rejection_reason',
            'requested_by', 'requested_by_name',
            'reviewed_by', 'reviewed_by_name',
            'reviewed_at', 'created_at',
        ]
        read_only_fields = [
            'id', 'status', 'rejection_reason',
            'requested_by', 'reviewed_by', 'reviewed_at', 'created_at',
        ]

    def get_skill_names(self, obj):
        return [skill.name for skill in obj.skills.all()]


class JobOpeningSerializer(serializers.ModelSerializer):

    department_name = serializers.CharField(source='department.name', read_only=True)
    location_name = serializers.CharField(source='location.name', read_only=True, allow_null=True)
    skill_names = serializers.SerializerMethodField()
    posted_by_name = serializers.CharField(source='posted_by.get_full_name', read_only=True)

    class Meta:
        model = JobOpening
        fields = [
            'id', 'vacancy_request',
            'title',
            'department', 'department_name',
            'location', 'location_name',
            'skills', 'skill_names',
            'vacancies', 'experience', 'description',
            # Structured JD fields
            'role_summary',
            'responsibilities',
            'required_skills_desc',
            'preferred_skills',
            'technologies',
            # Meta
            'status',
            'posted_by', 'posted_by_name',
            'posted_at', 'closed_at',
        ]
        read_only_fields = [
            'id', 'vacancy_request',
            'posted_by', 'posted_at', 'closed_at', 'status',
        ]

    def get_skill_names(self, obj):
        return [skill.name for skill in obj.skills.all()]