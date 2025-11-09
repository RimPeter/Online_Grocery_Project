from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('_catalog', '0008_homecategorytile'),
    ]

    operations = [
        migrations.AlterField(
            model_name='homecategorytile',
            name='l1',
            field=models.CharField(help_text='Parent category (sub_category) name shown on home page.', max_length=255, unique=True),
        ),
        migrations.AlterField(
            model_name='homecategorytile',
            name='l2',
            field=models.CharField(blank=True, help_text='(Legacy) optional child category name; ignored for main-category tiles.', max_length=255),
        ),
    ]
