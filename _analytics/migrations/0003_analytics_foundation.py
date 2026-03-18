from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('_analytics', '0002_rename__analytics_v_session_28884e_idx_danalytics__session_87cc58_idx'),
    ]

    operations = [
        migrations.AddField(
            model_name='visit',
            name='browser_family',
            field=models.CharField(blank=True, db_index=True, max_length=50),
        ),
        migrations.AddField(
            model_name='visit',
            name='device_type',
            field=models.CharField(blank=True, choices=[('desktop', 'Desktop'), ('mobile', 'Mobile'), ('tablet', 'Tablet'), ('bot', 'Bot'), ('other', 'Other')], db_index=True, max_length=20),
        ),
        migrations.AddField(
            model_name='visit',
            name='is_authenticated',
            field=models.BooleanField(db_index=True, default=False),
        ),
        migrations.AddField(
            model_name='visit',
            name='referrer_host',
            field=models.CharField(blank=True, db_index=True, max_length=255),
        ),
        migrations.AddField(
            model_name='visit',
            name='traffic_source',
            field=models.CharField(blank=True, choices=[('direct', 'Direct'), ('search', 'Search'), ('social', 'Social'), ('email', 'Email'), ('campaign', 'Campaign'), ('referral', 'Referral'), ('unknown', 'Unknown')], db_index=True, max_length=20),
        ),
        migrations.AddField(
            model_name='visit',
            name='utm_campaign',
            field=models.CharField(blank=True, db_index=True, max_length=255),
        ),
        migrations.AddField(
            model_name='visit',
            name='utm_content',
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name='visit',
            name='utm_medium',
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name='visit',
            name='utm_source',
            field=models.CharField(blank=True, db_index=True, max_length=255),
        ),
        migrations.AddField(
            model_name='visit',
            name='utm_term',
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.CreateModel(
            name='AnalyticsAnnotation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('event_date', models.DateField(db_index=True)),
                ('title', models.CharField(max_length=120)),
                ('note', models.TextField(blank=True)),
                ('color', models.CharField(blank=True, default='#0f7b6c', max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='analytics_annotations', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ('-event_date', '-created_at'),
            },
        ),
        migrations.CreateModel(
            name='AnalyticsSavedView',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=120)),
                ('config', models.JSONField(blank=True, default=dict)),
                ('is_default', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='analytics_saved_views', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ('name',),
                'unique_together': {('user', 'name')},
            },
        ),
        migrations.CreateModel(
            name='VisitPageview',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('session_key', models.CharField(db_index=True, max_length=40)),
                ('path', models.CharField(db_index=True, max_length=2048)),
                ('query', models.TextField(blank=True)),
                ('referrer', models.TextField(blank=True)),
                ('viewed_at', models.DateTimeField(db_index=True)),
                ('duration_seconds', models.PositiveIntegerField(blank=True, null=True)),
                ('sequence_index', models.PositiveIntegerField(default=1)),
                ('is_authenticated', models.BooleanField(db_index=True, default=False)),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='visit_pageviews', to=settings.AUTH_USER_MODEL)),
                ('visit', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='pageviews', to='_analytics.visit')),
            ],
            options={
                'ordering': ('-viewed_at',),
                'indexes': [
                    models.Index(fields=['visit', 'viewed_at'], name='analytics_vp_visit_idx'),
                    models.Index(fields=['path', 'viewed_at'], name='analytics_vp_path_idx'),
                    models.Index(fields=['session_key', 'viewed_at'], name='analytics_vp_session_idx'),
                ],
            },
        ),
        migrations.CreateModel(
            name='AnalyticsEvent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('session_key', models.CharField(blank=True, db_index=True, max_length=40)),
                ('event_type', models.CharField(db_index=True, max_length=64)),
                ('path', models.CharField(blank=True, db_index=True, max_length=2048)),
                ('label', models.CharField(blank=True, max_length=255)),
                ('value', models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True)),
                ('properties', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('pageview', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='events', to='_analytics.visitpageview')),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='analytics_events', to=settings.AUTH_USER_MODEL)),
                ('visit', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='events', to='_analytics.visit')),
            ],
            options={
                'ordering': ('-created_at',),
                'indexes': [
                    models.Index(fields=['event_type', 'created_at'], name='analytics_ev_type_idx'),
                    models.Index(fields=['session_key', 'created_at'], name='analytics_ev_session_idx'),
                ],
            },
        ),
    ]
