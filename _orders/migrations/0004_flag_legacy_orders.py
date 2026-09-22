from django.db import migrations


def flag_legacy_orders(apps, schema_editor):
    Order = apps.get_model('_orders', 'Order')
    Payment = apps.get_model('_payments', 'Payment')
    alias = schema_editor.connection.alias
    # Existing live intents require reconciliation before they can be retired safely.
    pending_payment_orders = Payment.objects.using(alias).filter(order__status='pending').values_list('order_id', flat=True)
    Order.objects.using(alias).filter(pk__in=pending_payment_orders).update(status='awaiting_payment')
    for order in Order.objects.using(alias).exclude(status='pending').iterator():
        snapshot = {}
        payments = list(Payment.objects.using(alias).filter(order_id=order.pk, status='succeeded'))
        if len(payments) == 1:
            snapshot = {'recorded_paid_total': str(payments[0].amount), 'currency': payments[0].currency}
        Order.objects.using(alias).filter(pk=order.pk).update(snapshot_needs_review=True, checkout_snapshot=snapshot)


class Migration(migrations.Migration):
    dependencies = [
        ('_orders', '0003_order_checkout_snapshot_order_snapshot_needs_review_and_more'),
        ('_payments', '0003_webhookevent_payment_attempt_key_and_more'),
    ]
    operations = [migrations.RunPython(flag_legacy_orders, migrations.RunPython.noop)]
