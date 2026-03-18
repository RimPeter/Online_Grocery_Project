from django.contrib import admin

from .models import AnalyticsAnnotation, AnalyticsEvent, AnalyticsSavedView, Visit, VisitPageview


@admin.register(Visit)
class VisitAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'started_at',
        'last_seen_at',
        'user',
        'landing_path',
        'traffic_source',
        'device_type',
        'browser_family',
    )
    list_filter = ('started_at', 'traffic_source', 'device_type', 'browser_family', 'is_authenticated')
    search_fields = ('session_key', 'user__email', 'landing_path', 'referrer', 'utm_campaign', 'utm_source')
    readonly_fields = (
        'session_key',
        'user',
        'started_at',
        'last_seen_at',
        'landing_path',
        'landing_query',
        'referrer',
        'referrer_host',
        'user_agent',
        'traffic_source',
        'device_type',
        'browser_family',
        'is_authenticated',
        'utm_source',
        'utm_medium',
        'utm_campaign',
        'utm_term',
        'utm_content',
    )
    ordering = ('-started_at',)


@admin.register(VisitPageview)
class VisitPageviewAdmin(admin.ModelAdmin):
    list_display = ('id', 'viewed_at', 'path', 'visit', 'duration_seconds', 'sequence_index')
    list_filter = ('viewed_at', 'is_authenticated')
    search_fields = ('path', 'query', 'session_key', 'visit__landing_path')
    readonly_fields = (
        'visit',
        'user',
        'session_key',
        'path',
        'query',
        'referrer',
        'viewed_at',
        'duration_seconds',
        'sequence_index',
        'is_authenticated',
    )
    ordering = ('-viewed_at',)


@admin.register(AnalyticsEvent)
class AnalyticsEventAdmin(admin.ModelAdmin):
    list_display = ('id', 'created_at', 'event_type', 'path', 'user', 'value')
    list_filter = ('event_type', 'created_at')
    search_fields = ('event_type', 'path', 'label', 'session_key', 'user__email')
    readonly_fields = (
        'visit',
        'pageview',
        'user',
        'session_key',
        'event_type',
        'path',
        'label',
        'value',
        'properties',
        'created_at',
    )
    ordering = ('-created_at',)


@admin.register(AnalyticsAnnotation)
class AnalyticsAnnotationAdmin(admin.ModelAdmin):
    list_display = ('event_date', 'title', 'created_by')
    list_filter = ('event_date',)
    search_fields = ('title', 'note')
    ordering = ('-event_date', '-created_at')


@admin.register(AnalyticsSavedView)
class AnalyticsSavedViewAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'is_default', 'updated_at')
    list_filter = ('is_default', 'updated_at')
    search_fields = ('name', 'user__email', 'user__username')
    ordering = ('user', 'name')
