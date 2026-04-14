from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from _catalog.models import All_Products
from _orders.models import Order
from _orders.pricing import calculate_checkout_totals
from _orders.notifications import send_paid_order_notification
from _product_management.templatetags.sum_tags import add_delivery_if_paid, checkout_grand_total, paid_order_grand_total


class BasketPricingTests(SimpleTestCase):
    def test_basket_reward_not_applied_below_threshold(self):
        pricing = calculate_checkout_totals(
            Decimal('94.99'),
            has_items=True,
            pricing_settings={
                'minimum_order_total': Decimal('40.00'),
                'delivery_charge': Decimal('1.50'),
                'discount_threshold': Decimal('95.00'),
                'discount_amount': Decimal('15.00'),
            },
        )

        self.assertEqual(pricing['basket_reward_discount'], Decimal('0.00'))
        self.assertEqual(pricing['minimum_order_total'], Decimal('40.00'))
        self.assertEqual(pricing['delivery_charge'], Decimal('1.50'))
        self.assertEqual(pricing['grand_total'], Decimal('96.49'))
        self.assertEqual(pricing['basket_reward_shortfall'], Decimal('0.01'))

    def test_basket_reward_applied_at_threshold(self):
        pricing = calculate_checkout_totals(
            Decimal('95.00'),
            has_items=True,
            pricing_settings={
                'minimum_order_total': Decimal('40.00'),
                'delivery_charge': Decimal('1.50'),
                'discount_threshold': Decimal('95.00'),
                'discount_amount': Decimal('15.00'),
            },
        )

        self.assertTrue(pricing['qualifies_for_basket_reward'])
        self.assertEqual(pricing['basket_reward_discount'], Decimal('15.00'))
        self.assertEqual(pricing['delivery_charge'], Decimal('1.50'))
        self.assertEqual(pricing['grand_total'], Decimal('81.50'))

    def test_paid_order_total_filter_uses_basket_reward(self):
        self.assertEqual(add_delivery_if_paid(Decimal('95.00'), 'paid'), Decimal('81.50'))
        self.assertEqual(add_delivery_if_paid(Decimal('95.00'), 'pending'), Decimal('95.00'))

    def test_checkout_grand_total_filter_applies_pending_discount(self):
        self.assertEqual(checkout_grand_total(Decimal('95.00')), Decimal('81.50'))
        self.assertEqual(checkout_grand_total(Decimal('94.99')), Decimal('96.49'))

    def test_checkout_totals_apply_referral_discounts_after_delivery(self):
        pricing = calculate_checkout_totals(
            Decimal('20.00'),
            has_items=True,
            pricing_settings={
                'minimum_order_total': Decimal('40.00'),
                'delivery_charge': Decimal('1.50'),
                'discount_threshold': Decimal('95.00'),
                'discount_amount': Decimal('15.00'),
            },
            newcomer_referral_discount=Decimal('5.00'),
            referral_credit_discount=Decimal('3.00'),
        )

        self.assertEqual(pricing['newcomer_referral_discount'], Decimal('5.00'))
        self.assertEqual(pricing['referral_credit_discount'], Decimal('3.00'))
        self.assertEqual(pricing['grand_total'], Decimal('13.50'))

    def test_paid_order_grand_total_filter_uses_order_referral_discounts(self):
        order = SimpleNamespace(
            computed_total=Decimal('20.00'),
            newcomer_referral_discount=Decimal('5.00'),
            referral_credit_discount=Decimal('3.00'),
        )

        self.assertEqual(paid_order_grand_total(order), Decimal('13.50'))


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    DEFAULT_FROM_EMAIL='no-reply@test.local',
)
class PaidOrderNotificationTests(SimpleTestCase):
    @patch('_orders.notifications.send_mail')
    def test_paid_order_notification_is_sent(self, send_mail_mock):
        order = SimpleNamespace(
            pk=7,
            id=7,
            status='paid',
            total=Decimal('95.00'),
            delivery_date=None,
            delivery_time=None,
            user=SimpleNamespace(
                get_full_name=lambda: 'Notify User',
                username='notify-user',
                email='customer@example.com',
                phone='0123456789',
            ),
            items=[],
        )

        self.assertTrue(send_paid_order_notification(order))
        send_mail_mock.assert_called_once()
        args = send_mail_mock.call_args.args
        self.assertIn('New paid order #7', args[0])
        self.assertEqual(args[3], ['primaszecsi@gmail.com'])

    @patch('_orders.notifications.send_mail')
    def test_paid_order_notification_skips_non_paid_orders(self, send_mail_mock):
        order = SimpleNamespace(pk=8, id=8, status='pending', total=Decimal('95.00'), items=[])

        self.assertFalse(send_paid_order_notification(order))
        send_mail_mock.assert_not_called()


class DeliverySlotsPricingTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='delivery-user',
            password='test-pass-123',
        )
        self.client.force_login(self.user)
        self.product = All_Products.objects.create(
            ga_product_id='ga-delivery-1',
            name='Threshold Product',
            price=Decimal('15.48'),
            list_position=1,
            url='https://example.com/products/threshold-product',
        )

    def test_delivery_slots_uses_customer_pricing_for_minimum_order_gate(self):
        session = self.client.session
        session['cart'] = {str(self.product.id): 2}
        session.save()

        response = self.client.get(reverse('delivery_slots'))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, '_orders/delivery_slots.html')

        order = Order.objects.get(user=self.user, status='pending')
        self.assertEqual(order.total, Decimal('40.24'))
        self.assertEqual(order.items.count(), 1)
        self.assertEqual(order.items.first().price, Decimal('20.12'))
