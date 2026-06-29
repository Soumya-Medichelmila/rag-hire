from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('recruitment', '0009_candidate_table'),
    ]

    operations = [
        migrations.AlterField(
            model_name='screeningresult',
            name='resume_source',
            field=models.CharField(
                choices=[
                    ('LOCAL', 'Local Folder'),
                    ('SHAREPOINT', 'SharePoint'),
                    ('UPLOAD', 'Direct Upload'),
                ],
                default='LOCAL',
                help_text='Where the resume was sourced from',
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name='interviewschedule',
            name='meeting_link',
            field=models.URLField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='interviewschedule',
            name='venue',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
    ]