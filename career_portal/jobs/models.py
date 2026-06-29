from django.db import models
from accounts.models import Employee
from masters.models import Department, Location, Skill


class VacancyRequest(models.Model):

    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('ACCEPTED', 'Accepted'),
        ('REJECTED', 'Rejected'),
    ]

    title = models.CharField(max_length=100)

    department = models.ForeignKey(
        Department, on_delete=models.PROTECT, related_name='vacancy_requests'
    )

    location = models.ForeignKey(
        Location, on_delete=models.PROTECT, related_name='vacancy_requests',
        null=True, blank=True
    )

    skills = models.ManyToManyField(Skill, related_name='vacancy_requests', blank=True)

    vacancies = models.PositiveIntegerField(default=1)

    experience = models.CharField(max_length=50, help_text='e.g. 2 years, 3-5 years')

    description = models.TextField(help_text='Reason for vacancy e.g. resignation, expansion')

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')

    rejection_reason = models.TextField(blank=True, null=True)

    requested_by = models.ForeignKey(
        Employee, on_delete=models.PROTECT, related_name='vacancy_requests_raised'
    )

    reviewed_by = models.ForeignKey(
        Employee, on_delete=models.PROTECT, related_name='vacancy_requests_reviewed',
        null=True, blank=True
    )

    reviewed_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.title} - {self.department.name} ({self.status})"


class JobOpening(models.Model):

    STATUS_CHOICES = [
        ('OPEN', 'Open'),
        ('CLOSED', 'Closed'),
    ]

    vacancy_request = models.OneToOneField(
        VacancyRequest, on_delete=models.PROTECT, related_name='job_opening'
    )

    title = models.CharField(max_length=100)

    department = models.ForeignKey(
        Department, on_delete=models.PROTECT, related_name='job_openings'
    )

    location = models.ForeignKey(
        Location, on_delete=models.PROTECT, related_name='job_openings',
        null=True, blank=True
    )

    skills = models.ManyToManyField(Skill, related_name='job_openings', blank=True)

    vacancies = models.PositiveIntegerField(default=1)

    experience = models.CharField(max_length=50)

    description = models.TextField()

    # ── Structured Job Description Fields ──────────────────────────
    role_summary = models.TextField(
        blank=True, null=True,
        help_text='Brief summary of the role'
    )

    responsibilities = models.TextField(
        blank=True, null=True,
        help_text='One responsibility per line'
    )

    required_skills_desc = models.TextField(
        blank=True, null=True,
        help_text='One required skill per line'
    )

    preferred_skills = models.TextField(
        blank=True, null=True,
        help_text='One preferred skill per line'
    )

    technologies = models.TextField(
        blank=True, null=True,
        help_text='One technology/stack item per line'
    )
    # ───────────────────────────────────────────────────────────────

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='OPEN')

    posted_by = models.ForeignKey(
        Employee, on_delete=models.PROTECT, related_name='job_openings_posted'
    )

    posted_at = models.DateTimeField(auto_now_add=True)

    closed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.title} - {self.department.name} ({self.status})"
    