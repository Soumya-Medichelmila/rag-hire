"""
recruitment/migrations/0002_screeningresult_resume_source.py
─────────────────────────────────────────────────────────────────────────────
Migration: adds resume_source field to ScreeningResult and updates
           unique_together to include it.

Run with:
    python manage.py migrate recruitment
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        # Replace "0001_initial" with your actual latest migration name
        ("recruitment", "0001_initial"),
    ]

    operations = [
        # 1. Add the new column with default='LOCAL' so existing rows are valid
        migrations.AddField(
            model_name="screeningresult",
            name="resume_source",
            field=models.CharField(
                choices=[("LOCAL", "Local Folder"), ("SHAREPOINT", "SharePoint")],
                default="LOCAL",
                help_text="Where the resume was sourced from",
                max_length=20,
            ),
        ),

        # 2. Drop the old unique_together constraint
        migrations.AlterUniqueTogether(
            name="screeningresult",
            unique_together=set(),
        ),

        # 3. Re-apply unique_together including the new field
        migrations.AlterUniqueTogether(
            name="screeningresult",
            unique_together={("job_opening", "source_filename", "resume_source")},
        ),
    ]