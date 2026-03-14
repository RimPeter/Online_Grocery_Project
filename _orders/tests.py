from decimal import Decimal

from django.test import SimpleTestCase

from _orders.pricing import calculate_checkout_totals
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
