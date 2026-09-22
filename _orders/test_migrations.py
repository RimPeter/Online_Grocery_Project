from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class HistoricalOrderMigrationTests(TransactionTestCase):
    def test_existing_payments_get_unique_keys_and_unknown_history_is_flagged(self):
        executor = MigrationExecutor(connection)
        latest = executor.loader.graph.leaf_nodes()
        old = [('_accounts', '0012_alter_user_referral_code'), ('_orders', '0002_order_referral_discounts'),
               ('_payments', '0002_alter_payment_currency')]
        try:
            executor.migrate(old)
            apps = executor.loader.project_state(old).apps
            user = apps.get_model('_accounts', 'User').objects.create(username='legacy', email='legacy@example.com', phone='123')
            Order = apps.get_model('_orders', 'Order')
            Payment = apps.get_model('_payments', 'Payment')
            paid = Order.objects.create(user=user, status='paid', total='52.00')
            pending = Order.objects.create(user=user, status='pending', total='52.00')
            Payment.objects.create(user=user, order=paid, amount='53.50', currency='gbp', status='succeeded')
            Payment.objects.create(user=user, order=pending, amount='53.50', currency='gbp', status='created')
            executor = MigrationExecutor(connection)
            executor.migrate(latest)
            apps = executor.loader.project_state(latest).apps
            Order = apps.get_model('_orders', 'Order')
            Payment = apps.get_model('_payments', 'Payment')
            paid = Order.objects.get(pk=paid.pk)
            pending = Order.objects.get(pk=pending.pk)
            self.assertTrue(paid.snapshot_needs_review)
            self.assertEqual(paid.checkout_snapshot, {'recorded_paid_total': '53.50', 'currency': 'gbp'})
            self.assertNotIn('address', paid.checkout_snapshot)
            self.assertEqual(pending.status, 'awaiting_payment')
            self.assertTrue(pending.snapshot_needs_review)
            self.assertEqual(len(set(Payment.objects.values_list('attempt_key', flat=True))), 2)
        finally:
            MigrationExecutor(connection).migrate(latest)
