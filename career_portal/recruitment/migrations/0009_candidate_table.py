from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('recruitment', '0008_merge_20260615_1224'),
    ]

    operations = [
        migrations.CreateModel(
            name='Candidate',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('full_name', models.CharField(help_text='Extracted via spaCy NER or filename fallback', max_length=150)),
                ('email', models.EmailField(blank=True, help_text='Extracted via Regex', null=True)),
                ('phone', models.CharField(blank=True, help_text='Extracted via Regex', max_length=20, null=True)),
                ('source_filename', models.CharField(help_text='Original uploaded filename', max_length=255)),
                ('sharepoint_filename', models.CharField(blank=True, help_text='Timestamped filename used in SharePoint', max_length=255, null=True)),
                ('is_embedded', models.BooleanField(default=False, help_text='True once resume chunks are stored in ChromaDB')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
    ]