from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('_catalog', '0017_productfavorite'),
    ]

    operations = [
        migrations.AlterField(
            model_name='homevaluepillar',
            name='subtitle',
            field=models.CharField(
                help_text='Supporting sentence shown under the heading.',
                max_length=310,
            ),
        ),
    ]
