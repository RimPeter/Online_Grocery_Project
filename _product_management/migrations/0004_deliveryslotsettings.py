from datetime import time
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("_product_management", "0003_subcategorypipelinerun"),
    ]

    operations = [
        migrations.CreateModel(
            name="DeliverySlotSettings",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("min_days_ahead", models.PositiveSmallIntegerField(default=1)),
                ("max_days_ahead", models.PositiveSmallIntegerField(default=14)),
                ("allow_same_day", models.BooleanField(default=False)),
                ("slot_start_time", models.TimeField(default=time(9, 0))),
                ("slot_end_time", models.TimeField(default=time(19, 0))),
                ("slot_step_minutes", models.PositiveSmallIntegerField(default=60)),
                ("slot_duration_hours", models.PositiveSmallIntegerField(default=3)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Delivery slot settings",
                "verbose_name_plural": "Delivery slot settings",
            },
        ),
    ]
