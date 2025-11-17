from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("_catalog", "0002_homesubcategory"),
    ]

    operations = [
        migrations.CreateModel(
            name="CategoryNodeSetting",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("main_category", models.CharField(blank=True, max_length=255)),
                ("sub_category", models.CharField(blank=True, max_length=255)),
                ("sub_subcategory", models.CharField(blank=True, max_length=255)),
                (
                    "is_visible_to_customers",
                    models.BooleanField(
                        db_index=True,
                        default=True,
                        help_text=(
                            "If unchecked and sub_subcategory is set, hides all products in that "
                            "leaf category from customers (staff/superusers still see them)."
                        ),
                    ),
                ),
                (
                    "sort_order",
                    models.PositiveIntegerField(
                        db_index=True,
                        default=0,
                        help_text="Optional sort order applied within a main/subcategory grouping.",
                    ),
                ),
                (
                    "heading_override",
                    models.CharField(
                        blank=True,
                        max_length=255,
                        help_text="Optional override for the label shown for this category node.",
                    ),
                ),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Category node setting",
                "verbose_name_plural": "Category node settings",
                "ordering": ("sort_order", "main_category", "sub_category", "sub_subcategory"),
                "unique_together": {("main_category", "sub_category", "sub_subcategory")},
            },
        ),
    ]
