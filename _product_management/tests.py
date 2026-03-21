from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from _catalog.models import All_Products
from _catalog.templatetags.price_tags import display_rsp
from _product_management.models import BasketPricingSettings


class BasketPricingSettingsTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='pm-admin',
            password='test-pass-123',
            is_staff=True,
        )
        self.client.force_login(self.user)

    def test_basket_pricing_settings_saves_rsp_multiplier(self):
        response = self.client.post(
            reverse('_product_management:basket_pricing_settings'),
            {
                'minimum_order_total': '40.00',
                'delivery_charge': '1.50',
                'discount_threshold': '95.00',
                'discount_amount': '15.00',
                'rsp_multiplier': '1.75',
            },
        )

        self.assertEqual(response.status_code, 302)
        settings_obj = BasketPricingSettings.get_solo()
        self.assertEqual(settings_obj.rsp_multiplier, Decimal('1.75'))

    def test_display_rsp_uses_configured_rsp_multiplier(self):
        settings_obj = BasketPricingSettings.get_solo()
        settings_obj.rsp_multiplier = Decimal('1.75')
        settings_obj.save(update_fields=['rsp_multiplier'])

        product = All_Products.objects.create(
            ga_product_id='ga-rsp-test-1',
            name='RSP Test Product',
            price=Decimal('2.00'),
            rsp=Decimal('9.99'),
            list_position=1,
            url='https://example.com/products/rsp-test',
        )

        self.assertEqual(display_rsp(product), Decimal('3.50'))
