from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('accounts', '0001_initial'),
        ('jobs', '0002_jobopening_jd_fields'),
    ]

    operations = [
        migrations.CreateModel(
            name='Resume',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('candidate_name', models.CharField(max_length=150)),
                ('file', models.FileField(upload_to='resumes/')),
                ('uploaded_at', models.DateTimeField(auto_now_add=True)),
                ('uploaded_by', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='uploaded_resumes',
                    to='accounts.employee'
                )),
            ],
        ),
        migrations.CreateModel(
            name='ScreeningResult',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('candidate_name', models.CharField(max_length=150)),
                ('match_score', models.PositiveIntegerField(help_text='Score out of 100')),
                ('reason', models.TextField(help_text='LLM explanation of match')),
                ('screened_at', models.DateTimeField(auto_now_add=True)),
                ('job_opening', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='screening_results',
                    to='jobs.jobopening'
                )),
                ('resume', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='screening_results',
                    to='recruitment.resume'
                )),
                ('screened_by', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='screening_results_triggered',
                    to='accounts.employee'
                )),
            ],
            options={
                'ordering': ['-match_score'],
                'unique_together': {('job_opening', 'resume')},
            },
        ),
    ]