from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('_accounts', '0007_contactmessageactive_contactmessagearchived_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='address',
            name='house_number',
            field=models.CharField(blank=True, max_length=20),
        ),
    ]
