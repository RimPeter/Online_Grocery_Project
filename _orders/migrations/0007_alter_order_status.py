# Generated by Django 5.1.2 on 2025-03-25 06:33

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('_orders', '0006_orderitem_supplier_completed'),
    ]

    operations = [
        migrations.AlterField(
            model_name='order',
            name='status',
            field=models.CharField(choices=[('pending', 'Pending'), ('paid', 'Paid'), ('processed', 'Processed'), ('delivered', 'Delivered'), ('canceled', 'Canceled')], default='pending', max_length=20),
        ),
    ]
