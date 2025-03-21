# Generated by Django 5.1.2 on 2024-11-19 07:32

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Supplier',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('company_name', models.CharField(max_length=255)),
                ('company_id', models.CharField(max_length=100, unique=True)),
                ('contact_person', models.CharField(blank=True, max_length=100, null=True)),
                ('email', models.EmailField(max_length=254)),
                ('phone', models.CharField(max_length=15)),
                ('house_number', models.CharField(max_length=10)),
                ('street_name1', models.CharField(max_length=100)),
                ('street_name2', models.CharField(blank=True, max_length=100, null=True)),
                ('city', models.CharField(max_length=50)),
                ('postal_code', models.CharField(max_length=20)),
                ('website', models.URLField(blank=True, null=True)),
                ('is_active', models.BooleanField(default=True)),
                ('bank_name', models.CharField(max_length=100)),
                ('bank_account', models.CharField(max_length=100)),
                ('sort_code', models.CharField(max_length=6)),
                ('VAT_number', models.CharField(max_length=100)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
        ),
    ]
