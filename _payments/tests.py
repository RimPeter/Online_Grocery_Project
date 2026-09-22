from datetime import time, timedelta
from decimal import Decimal
import hashlib
import hmac
import json
import time as clock
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db.models.deletion import ProtectedError
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from _accounts.models import Address, ReferralCreditLedger
from _accounts.referrals import get_available_referral_credit
from _catalog.models import All_Products
from _orders.models import Order, OrderItem
from _orders.snapshots import invoice_context
from _product_management.models import BasketPricingSettings
from .models import Payment, WebhookEvent
from .services import prepare_checkout, get_payment_intent, process_webhook, cancel_checkout, CheckoutError


class PaymentSafetyTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='buyer', password='password123',
            email='buyer@example.com', first_name='Test', last_name='Buyer', phone='07123456789')
        self.referrer = get_user_model().objects.create_user(username='referrer', email='referrer@example.com')
        self.address = Address.objects.create(user=self.user, street_address='Original Street', house_number='1',
            city='Kingston', postal_code='KT1 1AA', is_default=True)
        self.product = All_Products.objects.create(ga_product_id='1', name='Original Product', price=Decimal('10.00'),
            list_position=1, url='https://example.com/item')
        self.order = self.new_order()
        self.client.force_login(self.user)
        self.create_intent = patch('stripe.PaymentIntent.create', return_value={'id': 'pi_test', 'client_secret': 'secret'}).start()
        self.retrieve_intent = patch('stripe.PaymentIntent.retrieve', return_value={'id': 'pi_test', 'client_secret': 'secret'}).start()
        self.addCleanup(patch.stopall)

    def new_order(self):
        order = Order.objects.create(user=self.user, delivery_date=timezone.localdate() + timedelta(days=2), delivery_time=time(9))
        OrderItem.objects.create(order=order, product=self.product, quantity=4, price=Decimal('13.00'))
        order.refresh_from_db()
        return order

    def start(self):
        order, payment = prepare_checkout(self.user, self.order.pk)
        get_payment_intent(payment.pk)
        payment.refresh_from_db()
        return order, payment

    def event(self, payment, **overrides):
        intent = {'id': payment.stripe_payment_intent_id, 'metadata': {'payment_id': str(payment.pk)},
            'currency': payment.currency, 'amount': int(payment.amount * 100),
            'amount_received': int(payment.amount * 100), 'status': 'succeeded'}
        intent.update(overrides)
        return {'id': 'evt_test', 'type': 'payment_intent.succeeded', 'data': {'object': intent}}

    def post_event(self, event, signature=True):
        payload = json.dumps(event).encode()
        timestamp = str(int(clock.time()))
        digest = hmac.new(settings.STRIPE_WEBHOOK_SECRET.encode(), timestamp.encode() + b'.' + payload, hashlib.sha256).hexdigest()
        headers = {'HTTP_STRIPE_SIGNATURE': f't={timestamp},v1={digest}'} if signature else {}
        return Client(enforce_csrf_checks=True).post(reverse('stripe_webhook'), data=payload, content_type='application/json', **headers)

    def test_success_url_cannot_mark_unpaid_order_paid(self):
        order, payment = self.start()
        response = self.client.get(reverse('payment_success'), {'payment_id': payment.pk})
        order.refresh_from_db()
        self.assertEqual(order.status, 'awaiting_payment')
        self.assertContains(response, 'Payment not confirmed')
        self.assertFalse(ReferralCreditLedger.objects.exists())

    def test_get_checkout_does_not_create_payment(self):
        self.assertEqual(self.client.get(reverse('checkout', args=[self.order.pk])).status_code, 200)
        self.assertFalse(Payment.objects.exists())

    def test_browsing_cart_does_not_rewrite_order(self):
        item_id = self.order.items.get().pk
        self.client.get(reverse('cart_view'))
        self.assertEqual(self.order.items.get().pk, item_id)

    def test_normal_shopping_flow_creates_draft_on_delivery_post(self):
        self.order.delete()
        self.client.post(reverse('add_to_cart', args=[self.product.pk]), {'quantity': 4})
        self.client.get(reverse('cart_view'))
        self.client.get(reverse('delivery_slots'))
        self.assertFalse(Order.objects.filter(user=self.user).exists())
        response = self.client.post(reverse('delivery_slots'), {
            'delivery_date': (timezone.localdate() + timedelta(days=2)).isoformat(), 'delivery_time': '09:00'})
        order = Order.objects.get(user=self.user)
        self.assertEqual(response.url, reverse('order_summery', args=[order.pk]))
        self.assertEqual(self.client.post(reverse('checkout', args=[order.pk])).status_code, 200)

    def test_staff_pages_use_frozen_address_and_total(self):
        order, payment = self.start()
        process_webhook(self.event(payment))
        self.user.is_staff = True
        self.user.save()
        Address.objects.filter(pk=self.address.pk).update(street_address='Changed Address')
        BasketPricingSettings.objects.update(delivery_charge=99)
        response = self.client.get(reverse('_product_management:paid_orders'))
        self.assertContains(response, 'Original Street')
        self.assertContains(response, '53.50')
        self.assertNotContains(response, 'Changed Address')

    def test_staff_cannot_mark_unpaid_order_paid_or_delivered(self):
        self.user.is_staff = True
        self.user.save()
        for action in ('mark_order_paid', 'mark_order_processed', 'mark_order_completed'):
            self.client.post(reverse('_product_management:' + action, args=[self.order.pk]))
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'pending')

    def test_reorder_rejects_external_redirect(self):
        response = self.client.post(reverse('order_reorder', args=[self.order.pk]), {'return_to': 'https://evil.example/'})
        self.assertEqual(response.url, reverse('order_history'))

    def test_retry_after_network_error_keeps_idempotency_key(self):
        import stripe
        self.create_intent.side_effect = stripe.error.APIConnectionError('timeout')
        url = reverse('checkout', args=[self.order.pk])
        self.assertEqual(self.client.post(url).status_code, 503)
        payment = Payment.objects.get(order=self.order)
        first_key = self.create_intent.call_args.kwargs['idempotency_key']
        self.create_intent.side_effect = None
        self.assertEqual(self.client.post(url).status_code, 200)
        self.assertEqual(self.create_intent.call_args.kwargs['idempotency_key'], first_key)
        self.assertEqual(Payment.objects.get(order=self.order).pk, payment.pk)

    def test_post_checkout_freezes_order_and_refresh_reuses_intent(self):
        url = reverse('checkout', args=[self.order.pk])
        self.assertEqual(self.client.post(url).status_code, 200)
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(Payment.objects.count(), 1)
        self.create_intent.assert_called_once()
        self.assertIn('idempotency_key', self.create_intent.call_args.kwargs)

    def test_unknown_order_never_falls_back_to_cart(self):
        self.assertEqual(self.client.post(reverse('checkout', args=[99999])).status_code, 404)
        self.assertFalse(Payment.objects.exists())

    def test_signed_webhook_works_without_csrf_and_is_idempotent(self):
        self.user.referred_by = self.referrer
        self.user.save()
        order, payment = self.start()
        with patch('_payments.services.send_paid_order_notification') as notify:
            with self.captureOnCommitCallbacks(execute=True):
                self.assertEqual(self.post_event(self.event(payment)).status_code, 200)
                self.assertEqual(self.post_event(self.event(payment)).status_code, 200)
                event = self.event(payment)
                event['id'] = 'evt_second_delivery'
                self.assertEqual(self.post_event(event).status_code, 200)
            notify.assert_called_once()
        order.refresh_from_db()
        payment.refresh_from_db()
        self.assertEqual(order.status, 'paid')
        self.assertEqual(payment.status, 'succeeded')
        self.assertEqual(ReferralCreditLedger.objects.filter(entry_type='referrer_reward').count(), 1)

    def test_missing_invalid_signature_and_malformed_payload_rejected(self):
        _, payment = self.start()
        self.assertEqual(self.post_event(self.event(payment), signature=False).status_code, 400)
        response = Client(enforce_csrf_checks=True).post(reverse('stripe_webhook'), data='invalid', content_type='application/json', HTTP_STRIPE_SIGNATURE='invalid')
        self.assertEqual(response.status_code, 400)
        self.assertFalse(WebhookEvent.objects.exists())

    def test_wrong_amount_currency_intent_and_status_rejected(self):
        _, payment = self.start()
        for overrides in ({'amount': 1}, {'currency': 'usd'}, {'id': 'pi_stale'}, {'amount_received': 1}, {'status': 'processing'}):
            with self.subTest(overrides=overrides):
                self.assertEqual(self.post_event(self.event(payment, **overrides)).status_code, 400)
        payment.refresh_from_db()
        self.assertEqual(payment.status, 'created')

    def test_failed_event_cannot_downgrade_success(self):
        _, payment = self.start()
        process_webhook(self.event(payment))
        event = self.event(payment, status='requires_payment_method')
        event.update(id='evt_late_failure', type='payment_intent.payment_failed')
        process_webhook(event)
        payment.refresh_from_db()
        self.assertEqual(payment.status, 'succeeded')

    def test_retry_after_failed_payment_reuses_intent(self):
        _, payment = self.start()
        event = self.event(payment, status='requires_payment_method')
        event['type'] = 'payment_intent.payment_failed'
        process_webhook(event)
        get_payment_intent(payment.pk)
        self.create_intent.assert_called_once()
        self.retrieve_intent.assert_called_once()

    def test_minimum_address_slot_profile_and_hidden_product_validated(self):
        mutations = [
            (lambda: OrderItem.objects.filter(order=self.order).update(quantity=1), 'Minimum order'),
            (lambda: Address.objects.all().delete(), 'address'),
            (lambda: Order.objects.filter(pk=self.order.pk).update(delivery_date=None), 'delivery slot'),
            (lambda: get_user_model().objects.filter(pk=self.user.pk).update(phone=''), 'profile'),
            (lambda: All_Products.objects.filter(pk=self.product.pk).update(is_visible_to_customers=False), 'unavailable'),
        ]
        from django.db import transaction
        for mutate, expected in mutations:
            with self.subTest(expected=expected), transaction.atomic():
                mutate()
                with self.assertRaisesMessage(CheckoutError, expected):
                    prepare_checkout(self.user, self.order.pk)
                transaction.set_rollback(True)
        self.assertFalse(Payment.objects.exists())

    def test_changed_cart_requires_review(self):
        with self.assertRaisesMessage(CheckoutError, 'basket has changed'):
            prepare_checkout(self.user, self.order.pk, {str(self.product.pk): 5})

    def test_credit_reserved_and_second_checkout_blocked(self):
        ReferralCreditLedger.objects.create(user=self.user, entry_type='referrer_reward', amount=Decimal('10'))
        _, payment = self.start()
        self.assertEqual(payment.amount, Decimal('43.50'))
        self.assertEqual(get_available_referral_credit(self.user), Decimal('0'))
        another = self.new_order()
        with self.assertRaisesMessage(CheckoutError, 'existing payment'):
            prepare_checkout(self.user, another.pk)
        process_webhook(self.event(payment))
        self.assertEqual(get_available_referral_credit(self.user), Decimal('0'))
        self.assertEqual(ReferralCreditLedger.objects.filter(entry_type='credit_spent').count(), 1)

    @patch('stripe.PaymentIntent.cancel', return_value={'status': 'canceled'})
    def test_cancel_releases_credit_and_blocks_stale_success(self, cancel):
        ReferralCreditLedger.objects.create(user=self.user, entry_type='referrer_reward', amount=Decimal('10'))
        order, payment = self.start()
        cancel_checkout(self.user, payment.pk)
        self.assertEqual(get_available_referral_credit(self.user), Decimal('10'))
        with self.assertRaises(CheckoutError):
            process_webhook(self.event(payment))
        order.refresh_from_db()
        self.assertEqual(order.status, 'canceled')

    def test_zero_balance_completes_without_stripe(self):
        ReferralCreditLedger.objects.create(user=self.user, entry_type='referrer_reward', amount=Decimal('100'))
        response = self.client.post(reverse('checkout', args=[self.order.pk]))
        self.assertEqual(response.status_code, 302)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'paid')
        self.create_intent.assert_not_called()
        self.assertEqual(get_available_referral_credit(self.user), Decimal('46.50'))

    def test_frozen_invoice_survives_product_address_and_setting_changes(self):
        order, payment = self.start()
        process_webhook(self.event(payment))
        before = invoice_context(order)
        BasketPricingSettings.objects.update(delivery_charge=99, discount_amount=90)
        All_Products.objects.filter(pk=self.product.pk).update(name='Changed Product', vat_rate='zero')
        Address.objects.filter(pk=self.address.pk).update(street_address='Changed Street')
        order.refresh_from_db()
        self.assertEqual(invoice_context(order)['grand_total'], before['grand_total'])
        self.assertEqual(invoice_context(order)['default_address'].street_address, 'Original Street')
        self.assertEqual(order.items.first().display_name, 'Original Product')
        response = self.client.get(reverse('invoice_page', args=[order.pk]))
        self.assertContains(response, 'Original Street')
        self.assertContains(response, 'Original Product')
        pdf = self.client.get(reverse('invoice_pdf', args=[order.pk]))
        self.assertEqual(pdf.status_code, 200)
        self.assertTrue(pdf.content.startswith(b'%PDF'))

    def test_paid_order_and_products_cannot_be_deleted(self):
        order, payment = self.start()
        process_webhook(self.event(payment))
        self.client.post(reverse('order_delete', args=[order.pk]))
        self.assertTrue(Order.objects.filter(pk=order.pk).exists())
        self.assertTrue(Payment.objects.filter(pk=payment.pk).exists())
        with self.assertRaises(ProtectedError):
            self.product.delete()
        with self.assertRaises(ValidationError):
            order.delete()

    def test_account_deletion_retains_paid_order_and_payment(self):
        order, payment = self.start()
        process_webhook(self.event(payment))
        self.client.post(reverse('delete_account'), {'password': 'password123', 'confirm': 'DELETE'})
        order.refresh_from_db()
        payment.refresh_from_db()
        self.assertIsNone(order.user_id)
        self.assertIsNone(payment.user_id)
        self.assertEqual(order.status, 'paid')

    def test_frozen_items_cannot_be_edited(self):
        order, _ = self.start()
        item = order.items.first()
        item.quantity = 99
        with self.assertRaises(ValidationError):
            item.save()

    def test_customer_cannot_reschedule_frozen_order(self):
        order, _ = self.start()
        self.client.post(reverse('delivery_slots') + f'?order_id={order.pk}', {'delivery_date': '2099-01-01', 'delivery_time': '10:00'})
        order.refresh_from_db()
        self.assertEqual(order.delivery_time, time(9))

    def test_legacy_invoice_requires_review(self):
        Order.objects.filter(pk=self.order.pk).update(status='paid', snapshot_needs_review=True)
        self.assertEqual(self.client.get(reverse('invoice_page', args=[self.order.pk])).status_code, 409)
