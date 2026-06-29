from django.db import models


class Candidate(models.Model):

    # ── Personal Information ──────────────────────────────────────────────────
    full_name = models.CharField(
        max_length=150,
        help_text="Extracted via spaCy NER or filename fallback"
    )
    email = models.EmailField(
        blank=True, null=True,
        help_text="Extracted via Regex"
    )
    phone = models.CharField(
        max_length=20, blank=True, null=True,
        help_text="Extracted via Regex"
    )

    # ── Resume File Reference ─────────────────────────────────────────────────
    source_filename = models.CharField(
        max_length=255,
        help_text="Original uploaded filename"
    )
    sharepoint_filename = models.CharField(
        max_length=255, blank=True, null=True,
        help_text="Timestamped filename used in SharePoint"
    )

    # ── Resume file on disk (for SharePoint posting) ──────────────────────────
    resume_file = models.FileField(
        upload_to='resumes/',
        blank=True, null=True,
        help_text="Temp file on disk — deleted after SharePoint post"
    )

    # ── Embedding Status ──────────────────────────────────────────────────────
    is_embedded = models.BooleanField(
        default=False,
        help_text="True once resume chunks are stored in ChromaDB"
    )

    # ── SharePoint Status ─────────────────────────────────────────────────────
    is_posted_to_sharepoint = models.BooleanField(
        default=False,
        help_text="True once resume is posted to SharePoint after shortlisting"
    )

    # ── Timestamps ────────────────────────────────────────────────────────────
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.full_name} ({self.email or 'no email'})"