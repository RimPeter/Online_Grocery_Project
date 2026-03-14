from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("_product_management", "0004_deliveryslotsettings"),
    ]

    operations = [
        migrations.CreateModel(
            name="BasketPricingSettings",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("minimum_order_total", models.DecimalField(decimal_places=2, default=40, max_digits=10)),
                ("delivery_charge", models.DecimalField(decimal_places=2, default=1.5, max_digits=10)),
                ("discount_threshold", models.DecimalField(decimal_places=2, default=95, max_digits=10)),
                ("discount_amount", models.DecimalField(decimal_places=2, default=15, max_digits=10)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Basket pricing settings",
                "verbose_name_plural": "Basket pricing settings",
            },
        ),
    ]
