from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('_catalog', '0011_homevaluepillar'),
    ]

    operations = [
        migrations.AddField(
            model_name='all_products',
            name='is_visible_to_customers',
            field=models.BooleanField(
                default=True,
                db_index=True,
                help_text='If unchecked, product is hidden from customers but still visible to superusers.',
            ),
        ),
    ]

