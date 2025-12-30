from django.contrib import admin

from .models import Visit


@admin.register(Visit)
class VisitAdmin(admin.ModelAdmin):
    list_display = ('id', 'started_at', 'last_seen_at', 'user', 'landing_path')
    list_filter = ('started_at',)
    search_fields = ('session_key', 'user__email', 'landing_path', 'referrer')
    readonly_fields = (
        'session_key',
        'user',
        'started_at',
        'last_seen_at',
        'landing_path',
        'landing_query',
        'referrer',
        'user_agent',
    )
    ordering = ('-started_at',)

