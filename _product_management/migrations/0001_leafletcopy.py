from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="LeafletCopy",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("company_name", models.CharField(blank=True, default="Kingston Online Grocery", max_length=255)),
                ("company_tagline", models.CharField(blank=True, default="Fresh. Local. Delivered.", max_length=255)),
                ("headline", models.CharField(blank=True, default="Weekly Specials You'll Love", max_length=255)),
                ("bullet_1", models.CharField(blank=True, default="Hand-picked fresh produce every day", max_length=255)),
                ("bullet_2", models.CharField(blank=True, default="Great value essentials and pantry staples", max_length=255)),
                ("bullet_3", models.CharField(blank=True, default="Fast local delivery to your door", max_length=255)),
                ("cta_title", models.CharField(blank=True, default="Scan to Shop Online", max_length=255)),
                ("cta_subtitle", models.TextField(blank=True, default="Browse, order, and schedule delivery in minutes.")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Leaflet copy",
                "verbose_name_plural": "Leaflet copy",
            },
        ),
    ]

