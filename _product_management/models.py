from django.db import models
from django.utils import timezone
from datetime import time

from .constants import LEAFLET_TEXT_DEFAULTS


class LeafletCopy(models.Model):
    company_name = models.CharField(max_length=255, blank=True, default=LEAFLET_TEXT_DEFAULTS["company_name"])
    company_tagline = models.CharField(max_length=255, blank=True, default=LEAFLET_TEXT_DEFAULTS["company_tagline"])
    headline = models.CharField(max_length=255, blank=True, default=LEAFLET_TEXT_DEFAULTS["headline"])
    bullet_1 = models.CharField(max_length=255, blank=True, default=LEAFLET_TEXT_DEFAULTS["bullet_1"])
    bullet_2 = models.CharField(max_length=255, blank=True, default=LEAFLET_TEXT_DEFAULTS["bullet_2"])
    bullet_3 = models.CharField(max_length=255, blank=True, default=LEAFLET_TEXT_DEFAULTS["bullet_3"])
    cta_title = models.CharField(max_length=255, blank=True, default=LEAFLET_TEXT_DEFAULTS["cta_title"])
    cta_subtitle = models.TextField(blank=True, default=LEAFLET_TEXT_DEFAULTS["cta_subtitle"])
    default_site_url = models.CharField(max_length=500, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Leaflet copy"
        verbose_name_plural = "Leaflet copy"

    def __str__(self):
        return "Leaflet copy"

    @classmethod
    def get_solo(cls):
        defaults = dict(LEAFLET_TEXT_DEFAULTS)
        defaults["default_site_url"] = ""
        obj, _ = cls.objects.get_or_create(pk=1, defaults=defaults)
        return obj

    def as_dict(self):
        return {
            "company_name": self.company_name,
            "company_tagline": self.company_tagline,
            "headline": self.headline,
            "bullet_1": self.bullet_1,
            "bullet_2": self.bullet_2,
            "bullet_3": self.bullet_3,
            "cta_title": self.cta_title,
            "cta_subtitle": self.cta_subtitle,
            "default_site_url": self.default_site_url,
        }


class SubcategoryPipelineRun(models.Model):
    """Record metadata and errors for run_subcategory_pipeline executions."""

    started_at = models.DateTimeField(default=timezone.now, db_index=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    from_step = models.CharField(max_length=64, blank=True)
    to_step = models.CharField(max_length=64, blank=True)
    steps = models.TextField(
        blank=True,
        help_text="Comma-separated list of step names executed in this run.",
    )
    succeeded = models.BooleanField(default=False)
    errors = models.TextField(
        blank=True,
        help_text="Captured error messages for this pipeline run (if any).",
    )

    class Meta:
        ordering = ("-started_at",)
        verbose_name = "Subcategory pipeline run"
        verbose_name_plural = "Subcategory pipeline runs"

    def __str__(self):
        status = "ok" if self.succeeded else "failed"
        return f"Subcategory pipeline {status} at {self.started_at:%Y-%m-%d %H:%M:%S}"


class DeliverySlotSettings(models.Model):
    min_days_ahead = models.PositiveSmallIntegerField(default=1)
    max_days_ahead = models.PositiveSmallIntegerField(default=14)
    allow_same_day = models.BooleanField(default=False)
    slot_start_time = models.TimeField(default=time(9, 0))
    slot_end_time = models.TimeField(default=time(19, 0))
    slot_step_minutes = models.PositiveSmallIntegerField(default=60)
    slot_duration_hours = models.PositiveSmallIntegerField(default=3)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Delivery slot settings"
        verbose_name_plural = "Delivery slot settings"

    def __str__(self):
        return "Delivery slot settings"

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def effective_min_days_ahead(self):
        if self.allow_same_day:
            return int(self.min_days_ahead)
        return max(1, int(self.min_days_ahead))

    def effective_max_days_ahead(self):
        return max(int(self.max_days_ahead), self.effective_min_days_ahead())

    @staticmethod
    def _to_minutes(t):
        return (t.hour * 60) + t.minute

    @staticmethod
    def _value_from_minutes(minutes):
        h = minutes // 60
        m = minutes % 60
        return f"{h:02d}:{m:02d}"

    @staticmethod
    def _label_from_minutes(minutes):
        h24 = (minutes // 60) % 24
        m = minutes % 60
        suffix = "pm" if h24 >= 12 else "am"
        h12 = h24 % 12
        if h12 == 0:
            h12 = 12
        if m == 0:
            return f"{h12}{suffix}"
        return f"{h12}:{m:02d}{suffix}"

    def build_time_slot_options(self):
        start = self._to_minutes(self.slot_start_time)
        end = self._to_minutes(self.slot_end_time)
        step = int(self.slot_step_minutes or 60)
        duration = int(self.slot_duration_hours or 3) * 60

        if step <= 0:
            step = 60
        if duration <= 0:
            duration = 180
        if end < start:
            return []

        options = []
        cursor = start
        loops = 0
        while cursor <= end and loops < 200:
            finish = cursor + duration
            options.append(
                {
                    "value": self._value_from_minutes(cursor),
                    "label": f"{self._label_from_minutes(cursor)} - {self._label_from_minutes(finish)}",
                }
            )
            cursor += step
            loops += 1
        return options


class BasketPricingSettings(models.Model):
    minimum_order_total = models.DecimalField(max_digits=10, decimal_places=2, default=40)
    delivery_charge = models.DecimalField(max_digits=10, decimal_places=2, default=1.50)
    discount_threshold = models.DecimalField(max_digits=10, decimal_places=2, default=95)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=15)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Basket pricing settings"
        verbose_name_plural = "Basket pricing settings"

    def __str__(self):
        return "Basket pricing settings"

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
