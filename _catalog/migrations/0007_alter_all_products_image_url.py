# Generated by Django 5.1.2 on 2024-12-08 14:57

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('_catalog', '0006_alter_all_products_vat_rate'),
    ]

    operations = [
        migrations.AlterField(
            model_name='all_products',
            name='image_url',
            field=models.URLField(blank=True, db_index=True, null=True),
        ),
    ]
