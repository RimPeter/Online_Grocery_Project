from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from _orders.pricing import calculate_checkout_totals
from _orders.notifications import send_paid_order_notification
from _product_management.templatetags.sum_tags import add_delivery_if_paid, checkout_grand_total


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
