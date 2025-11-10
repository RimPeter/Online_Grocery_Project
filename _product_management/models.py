from django.db import models

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
