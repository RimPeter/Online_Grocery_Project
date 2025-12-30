from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Visit',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('session_key', models.CharField(db_index=True, max_length=40)),
                ('started_at', models.DateTimeField(db_index=True)),
                ('last_seen_at', models.DateTimeField(db_index=True)),
                ('landing_path', models.CharField(blank=True, max_length=2048)),
                ('landing_query', models.TextField(blank=True)),
                ('referrer', models.TextField(blank=True)),
                ('user_agent', models.TextField(blank=True)),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='visits', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ('-started_at',),
            },
        ),
        migrations.AddIndex(
            model_name='visit',
            index=models.Index(fields=['session_key', 'started_at'], name='_analytics_v_session_28884e_idx'),
        ),
    ]

