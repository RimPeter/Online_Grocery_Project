from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('_catalog', '0007_add_all_products_detail_fields'),
    ]

    operations = [
        migrations.CreateModel(
            name='HomeCategoryTile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('l1', models.CharField(help_text='Parent category/sub_category name (case-insensitive match).', max_length=255)),
                ('l2', models.CharField(help_text='Child category/sub_subcategory name (case-insensitive match).', max_length=255)),
                ('display_name', models.CharField(blank=True, help_text='Optional override for the label shown on the card.', max_length=255)),
                ('image_url', models.URLField(blank=True, help_text='Optional image URL; falls back to first product image if empty.')),
                ('is_active', models.BooleanField(db_index=True, default=True)),
                ('sort_order', models.PositiveIntegerField(db_index=True, default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Home category tile',
                'verbose_name_plural': 'Home category tiles',
                'ordering': ('sort_order', 'l1', 'l2'),
                'unique_together': {('l1', 'l2')},
            },
        ),
    ]
