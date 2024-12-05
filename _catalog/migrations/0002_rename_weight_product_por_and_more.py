# Generated by Django 5.1.2 on 2024-12-04 12:39

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('_catalog', '0001_initial'),
    ]

    operations = [
        migrations.RenameField(
            model_name='product',
            old_name='weight',
            new_name='por',
        ),
        migrations.RemoveField(
            model_name='product',
            name='is_available',
        ),
        migrations.RemoveField(
            model_name='product',
            name='lead_time_days',
        ),
        migrations.RemoveField(
            model_name='product',
            name='price',
        ),
        migrations.RemoveField(
            model_name='product',
            name='reorder_point',
        ),
        migrations.RemoveField(
            model_name='product',
            name='reorder_quantity',
        ),
        migrations.AddField(
            model_name='product',
            name='about_product',
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name='product',
            name='brand',
            field=models.CharField(blank=True, max_length=35),
        ),
        migrations.AddField(
            model_name='product',
            name='ingredients',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='product',
            name='other_information',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='product',
            name='pack_size',
            field=models.CharField(blank=True, max_length=10),
        ),
        migrations.AddField(
            model_name='product',
            name='product_code',
            field=models.CharField(blank=True, max_length=10),
        ),
        migrations.AddField(
            model_name='product',
            name='retail_EAN',
            field=models.CharField(blank=True, max_length=13),
        ),
        migrations.AddField(
            model_name='product',
            name='rsp',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True),
        ),
        migrations.AddField(
            model_name='product',
            name='vat_rate',
            field=models.CharField(choices=[('standard', 'Standard'), ('reduced', 'Reduced'), ('zero', 'Zero')], default='standard', max_length=10),
        ),
        migrations.AlterField(
            model_name='product',
            name='image',
            field=models.URLField(blank=True, max_length=500, null=True),
        ),
    ]