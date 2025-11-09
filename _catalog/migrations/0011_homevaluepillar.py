from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('_catalog', '0010_alter_homecategorytile_unique_together'),
    ]

    operations = [
        migrations.CreateModel(
            name='HomeValuePillar',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('key', models.CharField(help_text="Stable identifier used for seeding defaults (e.g., 'speed').", max_length=50, unique=True)),
                ('title', models.CharField(help_text='Short heading shown above the description.', max_length=255)),
                ('subtitle', models.CharField(help_text='Supporting sentence shown under the heading.', max_length=255)),
                ('sort_order', models.PositiveIntegerField(db_index=True, default=0)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Home value pillar',
                'verbose_name_plural': 'Home value pillars',
                'ordering': ('sort_order', 'id'),
            },
        ),
    ]
