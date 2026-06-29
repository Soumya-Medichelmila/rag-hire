from django.db import models
from accounts.models import Employee
from jobs.models import JobOpening
from .candidate_model import Candidate


class ScreeningResult(models.Model):

    RESUME_SOURCE_CHOICES = [
        ("LOCAL",      "Local Folder"),
        ("SHAREPOINT", "SharePoint"),
        ("UPLOAD",     "Direct Upload"),  # ← ADD THIS
    ]

    job_opening = models.ForeignKey(
        JobOpening,
        on_delete=models.CASCADE,
        related_name="screening_results",
    )
    source_filename = models.CharField(
        max_length=255,
        help_text="Filename inside the configured resume directory or SharePoint folder",
    )
    resume_source = models.CharField(
        max_length=20,
        choices=RESUME_SOURCE_CHOICES,
        default="LOCAL",
        help_text="Where the resume was sourced from",
    )
    candidate_name = models.CharField(max_length=150)
    candidate_email = models.EmailField(
        blank=True,
        null=True,
        help_text="Auto-extracted from resume file",
    )
    match_score = models.PositiveIntegerField(help_text="Score out of 100")
    reason = models.TextField(help_text="LLM explanation of match")
    screened_at = models.DateTimeField(auto_now_add=True)
    screened_by = models.ForeignKey(
        Employee,
        on_delete=models.PROTECT,
        related_name="screening_results_triggered",
    )

    class Meta:
        ordering = ["-match_score"]
        unique_together = [["job_opening", "source_filename", "resume_source"]]

    def __str__(self):
        return (
            f"{self.candidate_name} — {self.job_opening.title} "
            f"({self.match_score}%) [{self.resume_source}]"
        )


class Shortlist(models.Model):
    job_opening = models.ForeignKey(
        JobOpening,
        on_delete=models.CASCADE,
        related_name="shortlisted_candidates",
    )
    screening_result = models.OneToOneField(
        ScreeningResult,
        on_delete=models.CASCADE,
        related_name="shortlist",
    )
    shortlisted_by = models.ForeignKey(
        Employee,
        on_delete=models.PROTECT,
        related_name="shortlisted_candidates",
    )
    shortlisted_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True, null=True)

    STATUS_CHOICES = [
        ("SHORTLISTED", "Shortlisted"),
        ("SCHEDULED",   "Scheduled"),
        ("HIRED",       "Hired"),
        ("REJECTED",    "Rejected"),
    ]
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="SHORTLISTED"
    )

    def __str__(self):
        return (
            f"{self.screening_result.candidate_name} "
            f"shortlisted for {self.job_opening.title}"
        )


class InterviewSchedule(models.Model):

    MODE_CHOICES = [
        ("ONLINE",  "Online"),
        ("OFFLINE", "Offline"),
    ]

    STATUS_CHOICES = [
        ("SCHEDULED",  "Scheduled"),
        ("COMPLETED",  "Completed"),
        ("CANCELLED",  "Cancelled"),
    ]

    shortlist = models.ForeignKey(
        Shortlist,
        on_delete=models.CASCADE,
        related_name="interviews",
    )
    interview_date = models.DateField()
    interview_time = models.TimeField()
    mode = models.CharField(max_length=10, choices=MODE_CHOICES, default="ONLINE")
    meeting_link = models.URLField(blank=True, null=True)
    venue = models.CharField(max_length=255, blank=True, null=True)
    assigned_interviewer = models.ForeignKey(
        Employee,
        on_delete=models.PROTECT,
        related_name="assigned_interviews",
    )
    notes = models.TextField(blank=True, null=True)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="SCHEDULED"
    )
    email_sent = models.BooleanField(default=False)
    scheduled_by = models.ForeignKey(
        Employee,
        on_delete=models.PROTECT,
        related_name="scheduled_interviews",
    )
    scheduled_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return (
            f"Interview for {self.shortlist.screening_result.candidate_name} "
            f"on {self.interview_date}"
        )