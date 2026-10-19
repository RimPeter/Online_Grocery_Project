from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('_payments', '0003_webhookevent_payment_attempt_key_and_more')]

    operations = [
        migrations.CreateModel(
            name='PaymentSettings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('checkout_payments_enabled', models.BooleanField(default=True)),
            ],
        ),
    ]
