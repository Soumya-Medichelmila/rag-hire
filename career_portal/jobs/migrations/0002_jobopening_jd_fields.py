from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        # Replace 'XXXX' with your last migration number, e.g. ('jobs', '0001_initial')
        ('jobs', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='jobopening',
            name='role_summary',
            field=models.TextField(blank=True, null=True, help_text='Brief summary of the role'),
        ),
        migrations.AddField(
            model_name='jobopening',
            name='responsibilities',
            field=models.TextField(blank=True, null=True, help_text='One responsibility per line'),
        ),
        migrations.AddField(
            model_name='jobopening',
            name='required_skills_desc',
            field=models.TextField(blank=True, null=True, help_text='One required skill per line'),
        ),
        migrations.AddField(
            model_name='jobopening',
            name='preferred_skills',
            field=models.TextField(blank=True, null=True, help_text='One preferred skill per line'),
        ),
        migrations.AddField(
            model_name='jobopening',
            name='technologies',
            field=models.TextField(blank=True, null=True, help_text='One technology/stack item per line'),
        ),
    ]