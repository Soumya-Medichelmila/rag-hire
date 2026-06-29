from django.contrib import admin
from .models import ScreeningResult, Shortlist, InterviewSchedule


@admin.register(ScreeningResult)
class ScreeningResultAdmin(admin.ModelAdmin):
    list_display = ('candidate_name', 'job_opening', 'match_score', 'screened_at')
    list_filter = ('job_opening', 'screened_at')
    search_fields = ('candidate_name', 'source_filename', 'candidate_email')
    readonly_fields = ('screened_at',)


@admin.register(Shortlist)
class ShortlistAdmin(admin.ModelAdmin):
    list_display = ('screening_result', 'job_opening', 'shortlisted_by', 'shortlisted_at')
    list_filter = ('job_opening', 'shortlisted_at')
    raw_id_fields = ('screening_result', 'shortlisted_by')


@admin.register(InterviewSchedule)
class InterviewScheduleAdmin(admin.ModelAdmin):
    list_display = ('get_candidate_name', 'get_job_title', 'interview_date', 'interview_time', 'status')
    list_filter = ('status', 'mode', 'interview_date')
    date_hierarchy = 'interview_date'

    def get_candidate_name(self, obj):
        return obj.shortlist.screening_result.candidate_name
    get_candidate_name.short_description = 'Candidate'

    def get_job_title(self, obj):
        return obj.shortlist.job_opening.title
    get_job_title.short_description = 'Job Opening'