

from rest_framework import serializers
from .models import ScreeningResult, Shortlist, InterviewSchedule


class ScreeningResultSerializer(serializers.ModelSerializer):
    job_title        = serializers.CharField(source="job_opening.title", read_only=True)
    screened_by_name = serializers.CharField(
        source="screened_by.user.get_full_name", read_only=True
    )
    is_shortlisted   = serializers.SerializerMethodField()
    shortlist_id     = serializers.SerializerMethodField()

    class Meta:
        model  = ScreeningResult
        fields = [
            "id",
            "job_opening",
            "job_title",
            "source_filename",
            "resume_source",          # ← NEW
            "candidate_name",
            "candidate_email",
            "match_score",
            "reason",
            "screened_at",
            "screened_by",
            "screened_by_name",
            "is_shortlisted",
            "shortlist_id",
        ]
        read_only_fields = fields

    def get_is_shortlisted(self, obj):
        return hasattr(obj, "shortlist")

    def get_shortlist_id(self, obj):
        return obj.shortlist.id if hasattr(obj, "shortlist") else None


class ShortlistSerializer(serializers.ModelSerializer):
    candidate_name      = serializers.CharField(source="screening_result.candidate_name",  read_only=True)
    candidate_email     = serializers.CharField(source="screening_result.candidate_email", read_only=True)
    match_score         = serializers.IntegerField(source="screening_result.match_score",  read_only=True)
    reason              = serializers.CharField(source="screening_result.reason",          read_only=True)
    source_filename     = serializers.CharField(source="screening_result.source_filename", read_only=True)
    resume_source       = serializers.CharField(source="screening_result.resume_source",   read_only=True)  # ← NEW
    job_title           = serializers.CharField(source="job_opening.title",                read_only=True)
    shortlisted_by_name = serializers.CharField(
        source="shortlisted_by.user.get_full_name", read_only=True
    )
    screening_result_id = serializers.IntegerField(source="screening_result.id", read_only=True)
    has_interview       = serializers.SerializerMethodField()
    interview_count     = serializers.SerializerMethodField()
    status              = serializers.CharField(read_only=True)

    class Meta:
        model  = Shortlist
        fields = [
            "id",
            "job_opening",
            "job_title",
            "screening_result_id",
            "source_filename",
            "resume_source",          # ← NEW
            "candidate_name",
            "candidate_email",
            "match_score",
            "reason",
            "shortlisted_by",
            "shortlisted_by_name",
            "shortlisted_at",
            "notes",
            "has_interview",
            "interview_count",
            "status",
        ]
        read_only_fields = fields

    def get_has_interview(self, obj):
        return obj.interviews.exists()

    def get_interview_count(self, obj):
        return obj.interviews.count()


class InterviewScheduleSerializer(serializers.ModelSerializer):
    candidate_name    = serializers.CharField(
        source="shortlist.screening_result.candidate_name",  read_only=True)
    candidate_email   = serializers.CharField(
        source="shortlist.screening_result.candidate_email", read_only=True)
    source_filename   = serializers.CharField(
        source="shortlist.screening_result.source_filename", read_only=True)
    resume_source     = serializers.CharField(
        source="shortlist.screening_result.resume_source",   read_only=True)   # ← NEW
    job_title         = serializers.CharField(
        source="shortlist.job_opening.title", read_only=True)
    match_score       = serializers.IntegerField(
        source="shortlist.screening_result.match_score", read_only=True)
    interviewer_name  = serializers.CharField(
        source="assigned_interviewer.user.get_full_name", read_only=True)
    interviewer_email = serializers.CharField(
        source="assigned_interviewer.user.email", read_only=True, default="")
    scheduled_by_name = serializers.CharField(
        source="scheduled_by.user.get_full_name", read_only=True)

    class Meta:
        model  = InterviewSchedule
        fields = [
            "id",
            "shortlist",
            "candidate_name",
            "candidate_email",
            "source_filename",
            "resume_source",          # ← NEW
            "job_title",
            "match_score",
            "interview_date",
            "interview_time",
            "mode",
            "meeting_link",
            "venue",
            "assigned_interviewer",
            "interviewer_name",
            "interviewer_email",
            "notes",
            "status",
            "email_sent",
            "scheduled_by",
            "scheduled_by_name",
            "scheduled_at",
        ]
        read_only_fields = [
            "candidate_name", "candidate_email", "source_filename",
            "resume_source", "job_title", "match_score",
            "interviewer_name", "interviewer_email",
            "scheduled_by_name", "scheduled_at",
        ]
