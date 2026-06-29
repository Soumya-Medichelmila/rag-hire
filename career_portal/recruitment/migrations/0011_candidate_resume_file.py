from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('recruitment', '0010_add_upload_source'),
    ]

    operations = [
        migrations.AddField(
            model_name='candidate',
            name='resume_file',
            field=models.FileField(
                blank=True, null=True,
                upload_to='resumes/',
                help_text='Temp file on disk — deleted after SharePoint post'
            ),
        ),
        migrations.AddField(
            model_name='candidate',
            name='is_posted_to_sharepoint',
            field=models.BooleanField(
                default=False,
                help_text='True once resume is posted to SharePoint after shortlisting'
            ),
        ),
    ]