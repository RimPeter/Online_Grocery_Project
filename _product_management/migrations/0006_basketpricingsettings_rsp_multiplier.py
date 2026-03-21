from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("_product_management", "0005_basketpricingsettings"),
    ]

    operations = [
        migrations.AddField(
            model_name="basketpricingsettings",
            name="rsp_multiplier",
            field=models.DecimalField(decimal_places=2, default=1.3, max_digits=10),
        ),
    ]
