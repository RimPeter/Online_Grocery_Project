from django.conf import settings
from django.db import models


class Visit(models.Model):
    session_key = models.CharField(max_length=40, db_index=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='visits',
    )
    started_at = models.DateTimeField(db_index=True)
    last_seen_at = models.DateTimeField(db_index=True)
    landing_path = models.CharField(max_length=2048, blank=True)
    landing_query = models.TextField(blank=True)
    referrer = models.TextField(blank=True)
    user_agent = models.TextField(blank=True)

    class Meta:
        ordering = ('-started_at',)
        indexes = [
            models.Index(fields=['session_key', 'started_at']),
        ]

    def __str__(self):
        return f'Visit #{self.pk} ({self.session_key})'

