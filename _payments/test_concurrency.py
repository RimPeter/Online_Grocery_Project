from concurrent.futures import ThreadPoolExecutor
from datetime import time, timedelta
from decimal import Decimal
from threading import Barrier
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import close_old_connections
from django.test import TransactionTestCase, skipUnlessDBFeature
from django.utils import timezone

from _accounts.models import Address, ReferralCreditLedger
from _accounts.referrals import get_available_referral_credit
from _catalog.models import All_Products
from _orders.models import Order, OrderItem
from .models import Payment
from .services import CheckoutError, prepare_checkout, process_webhook


@skipUnlessDBFeature('has_select_for_update')
class PaymentConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='parallel', email='parallel@example.com',
            first_name='Parallel', last_name='Buyer', phone='123')
        Address.objects.create(user=self.user, street_address='Street', house_number='1', city='Kingston', postal_code='KT1')
        product = All_Products.objects.create(name='Product', ga_product_id='parallel', price=10, list_position=1)
        self.orders = []
        for _ in range(2):
            order = Order.objects.create(user=self.user, delivery_date=timezone.localdate() + timedelta(days=2), delivery_time=time(9))
            OrderItem.objects.create(order=order, product=product, price=13, quantity=4)
            self.orders.append(order)
        ReferralCreditLedger.objects.create(user=self.user, entry_type='referrer_reward', amount=10)
        # Avoid unrelated singleton creation races in this focused lock test.
        from _product_management.models import BasketPricingSettings, DeliverySlotSettings
        BasketPricingSettings.get_solo()
        DeliverySlotSettings.get_solo()

    def test_parallel_checkouts_cannot_reserve_same_credit(self):
        barrier = Barrier(2)
        def checkout(order):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                try:
                    prepare_checkout(self.user, order.pk)
                    return 'created'
                except CheckoutError:
                    return 'blocked'
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(checkout, self.orders))
        self.assertCountEqual(results, ['created', 'blocked'])
        self.assertEqual(Payment.objects.count(), 1)
        self.assertEqual(get_available_referral_credit(self.user), Decimal('0'))

    @patch('_payments.services.send_paid_order_notification')
    def test_parallel_webhooks_spend_credit_and_notify_once(self, notify):
        order, payment = prepare_checkout(self.user, self.orders[0].pk)
        payment.stripe_payment_intent_id = 'pi_parallel'
        payment.save()
        event = {'id': 'evt_parallel', 'type': 'payment_intent.succeeded', 'data': {'object': {
            'id': 'pi_parallel', 'status': 'succeeded', 'amount': 4350, 'amount_received': 4350,
            'currency': 'gbp', 'metadata': {'payment_id': str(payment.pk)}}}}
        barrier = Barrier(2)
        def deliver(_):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                process_webhook(event)
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(deliver, range(2)))
        self.assertEqual(ReferralCreditLedger.objects.filter(entry_type='credit_spent').count(), 1)
        notify.assert_called_once()
