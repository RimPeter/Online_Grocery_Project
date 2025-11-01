from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("_catalog", "0005_all_productsmissingrsp"),
    ]

    operations = [
        migrations.AlterField(
            model_name="all_products",
            name="retail_EAN",
            field=models.CharField(max_length=18, blank=True),
        ),
    ]

