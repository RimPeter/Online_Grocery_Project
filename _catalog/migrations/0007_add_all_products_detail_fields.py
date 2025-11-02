from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("_catalog", "0006_alter_all_products_retail_ean_length"),
    ]

    operations = [
        migrations.AddField(
            model_name="all_products",
            name="description",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="all_products",
            name="ingredients_nutrition",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="all_products",
            name="other_info",
            field=models.TextField(blank=True),
        ),
    ]

