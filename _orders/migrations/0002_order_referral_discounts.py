from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('_orders', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='newcomer_referral_discount',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10),
        ),
        migrations.AddField(
            model_name='order',
            name='referral_credit_discount',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10),
        ),
    ]
