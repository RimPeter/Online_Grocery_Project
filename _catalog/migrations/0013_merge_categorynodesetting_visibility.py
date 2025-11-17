from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("_catalog", "0003_categorynodesetting"),
        ("_catalog", "0012_all_products_is_visible_to_customers"),
    ]

    operations = [
        # Merge migration – no schema changes; it just joins the branches.
    ]

