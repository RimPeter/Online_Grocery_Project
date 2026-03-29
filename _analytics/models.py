from django.conf import settings
from django.db import models


class Visit(models.Model):
    SOURCE_CHOICES = [
        ('direct', 'Direct'),
        ('search', 'Search'),
        ('social', 'Social'),
        ('email', 'Email'),
        ('campaign', 'Campaign'),
        ('referral', 'Referral'),
        ('unknown', 'Unknown'),
    ]
    DEVICE_CHOICES = [
        ('desktop', 'Desktop'),
        ('mobile', 'Mobile'),
        ('tablet', 'Tablet'),
        ('bot', 'Bot'),
        ('other', 'Other'),
    ]

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
    referrer_host = models.CharField(max_length=255, blank=True, db_index=True)
    user_agent = models.TextField(blank=True)
    traffic_source = models.CharField(max_length=20, blank=True, choices=SOURCE_CHOICES, db_index=True)
    device_type = models.CharField(max_length=20, blank=True, choices=DEVICE_CHOICES, db_index=True)
    browser_family = models.CharField(max_length=50, blank=True, db_index=True)
    is_authenticated = models.BooleanField(default=False, db_index=True)
    utm_source = models.CharField(max_length=255, blank=True, db_index=True)
    utm_medium = models.CharField(max_length=255, blank=True)
    utm_campaign = models.CharField(max_length=255, blank=True, db_index=True)
    utm_term = models.CharField(max_length=255, blank=True)
    utm_content = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ('-started_at',)
        indexes = [
            models.Index(fields=['session_key', 'started_at']),
        ]

    def __str__(self):
        return f'Visit #{self.pk} ({self.session_key})'


class VisitPageview(models.Model):
    visit = models.ForeignKey(Visit, on_delete=models.CASCADE, related_name='pageviews')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='visit_pageviews',
    )
    session_key = models.CharField(max_length=40, db_index=True)
    path = models.CharField(max_length=2048, db_index=True)
    query = models.TextField(blank=True)
    referrer = models.TextField(blank=True)
    viewed_at = models.DateTimeField(db_index=True)
    duration_seconds = models.PositiveIntegerField(null=True, blank=True)
    sequence_index = models.PositiveIntegerField(default=1)
    is_authenticated = models.BooleanField(default=False, db_index=True)

    class Meta:
        ordering = ('-viewed_at',)
        indexes = [
            models.Index(fields=['visit', 'viewed_at']),
            models.Index(fields=['path', 'viewed_at']),
            models.Index(fields=['session_key', 'viewed_at']),
        ]

    def __str__(self):
        return f'Pageview #{self.pk} ({self.path})'


class AnalyticsEvent(models.Model):
    visit = models.ForeignKey(
        Visit,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='events',
    )
    pageview = models.ForeignKey(
        VisitPageview,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='events',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='analytics_events',
    )
    session_key = models.CharField(max_length=40, blank=True, db_index=True)
    event_type = models.CharField(max_length=64, db_index=True)
    path = models.CharField(max_length=2048, blank=True, db_index=True)
    label = models.CharField(max_length=255, blank=True)
    value = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    properties = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ('-created_at',)
        indexes = [
            models.Index(fields=['event_type', 'created_at']),
            models.Index(fields=['session_key', 'created_at']),
        ]

    def __str__(self):
        return f'{self.event_type} #{self.pk}'


class GoogleAdsLandingArrival(models.Model):
    visit = models.OneToOneField(
        Visit,
        on_delete=models.CASCADE,
        related_name='google_ads_arrival',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='google_ads_landing_arrivals',
    )
    session_key = models.CharField(max_length=40, blank=True, db_index=True)
    path = models.CharField(max_length=2048, blank=True, db_index=True)
    arrived_at = models.DateTimeField(db_index=True)
    traffic_source = models.CharField(max_length=20, blank=True, choices=Visit.SOURCE_CHOICES, db_index=True)
    device_type = models.CharField(max_length=20, blank=True, choices=Visit.DEVICE_CHOICES, db_index=True)
    browser_family = models.CharField(max_length=50, blank=True, db_index=True)
    is_authenticated = models.BooleanField(default=False, db_index=True)
    utm_source = models.CharField(max_length=255, blank=True, db_index=True)
    utm_medium = models.CharField(max_length=255, blank=True)
    utm_campaign = models.CharField(max_length=255, blank=True, db_index=True)
    referrer_host = models.CharField(max_length=255, blank=True, db_index=True)

    class Meta:
        ordering = ('-arrived_at',)
        indexes = [
            models.Index(fields=['path', 'arrived_at']),
            models.Index(fields=['session_key', 'arrived_at']),
        ]

    def __str__(self):
        return f'Google Ads arrival #{self.pk} ({self.path})'


class AnalyticsAnnotation(models.Model):
    event_date = models.DateField(db_index=True)
    title = models.CharField(max_length=120)
    note = models.TextField(blank=True)
    color = models.CharField(max_length=20, blank=True, default='#0f7b6c')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='analytics_annotations',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-event_date', '-created_at')

    def __str__(self):
        return f'{self.event_date}: {self.title}'


class AnalyticsSavedView(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='analytics_saved_views',
    )
    name = models.CharField(max_length=120)
    config = models.JSONField(default=dict, blank=True)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('name',)
        unique_together = [('user', 'name')]

    def __str__(self):
        return f'{self.user_id}: {self.name}'
