import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def generate_code():
    return uuid.uuid4().hex[:10].upper()


def backfill_referral_codes(apps, schema_editor):
    User = apps.get_model('_accounts', 'User')
    used_codes = set(
        User.objects.exclude(referral_code__isnull=True)
        .exclude(referral_code='')
        .values_list('referral_code', flat=True)
    )

    for user in User.objects.all().iterator():
        if user.referral_code:
            continue
        code = generate_code()
        while code in used_codes:
            code = generate_code()
        user.referral_code = code
        user.save(update_fields=['referral_code'])
        used_codes.add(code)


class Migration(migrations.Migration):

    dependencies = [
        ('_orders', '0002_order_referral_discounts'),
        ('_accounts', '0010_allow_multi_use_test_email'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='referral_code',
            field=models.CharField(blank=True, max_length=10, null=True),
        ),
        migrations.AddField(
            model_name='user',
            name='referred_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=models.SET_NULL, related_name='referrals', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='pendingsignup',
            name='referral_code',
            field=models.CharField(blank=True, max_length=10),
        ),
        migrations.CreateModel(
            name='ReferralCreditLedger',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('entry_type', models.CharField(choices=[('referrer_reward', 'Referrer reward'), ('credit_spent', 'Credit spent')], max_length=32)),
                ('amount', models.DecimalField(decimal_places=2, max_digits=10)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('order', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='referral_credit_entries', to='_orders.order')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='referral_credit_entries', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['created_at', 'id'],
            },
        ),
        migrations.RunPython(backfill_referral_codes, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='user',
            name='referral_code',
            field=models.CharField(default=generate_code, editable=False, max_length=10, unique=True),
        ),
        migrations.AddConstraint(
            model_name='referralcreditledger',
            constraint=models.UniqueConstraint(fields=('user', 'order', 'entry_type'), name='uniq_referral_credit_entry_per_order_type'),
        ),
    ]
