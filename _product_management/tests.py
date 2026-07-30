from decimal import Decimal

from bs4 import BeautifulSoup
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from _catalog.models import All_Products
from _catalog.templatetags.price_tags import display_rsp
from _product_management.management.commands.scraper_for_sub_subcategory import (
    Command as ProductScraperCommand,
)
from _product_management.models import BasketPricingSettings


class ProductScraperPaginationTests(SimpleTestCase):
    def test_current_subcategory_input_is_supported(self):
        data = {
            "Bread & Cakes": {
                "Bread & Morning Goods": (
                    "https://www.bestwaywholesale.co.uk/bread-cakes/401"
                )
            }
        }

        self.assertEqual(
            list(ProductScraperCommand._expand_urls(data)),
            [
                (
                    "Bread & Cakes",
                    "Bread & Morning Goods",
                    "",
                    "https://www.bestwaywholesale.co.uk/bread-cakes/401",
                )
            ],
        )

    def test_stale_offset_is_removed_from_listing_root(self):
        root = ProductScraperCommand._listing_root_url(
            "https://www.bestwaywholesale.co.uk/bread-cakes/401?s=700",
            "https://www.bestwaywholesale.co.uk",
        )

        self.assertEqual(
            root,
            "https://www.bestwaywholesale.co.uk/bread-cakes/401",
        )

    def test_listing_count_generates_twenty_product_offsets(self):
        soup = BeautifulSoup(
            "<p>Displaying products 1 to 20 of 112 Products:</p>",
            "html.parser",
        )

        urls = ProductScraperCommand._listing_page_urls(
            "https://www.bestwaywholesale.co.uk/bread-cakes/401",
            soup,
        )

        self.assertEqual(
            urls,
            [
                "https://www.bestwaywholesale.co.uk/bread-cakes/401",
                "https://www.bestwaywholesale.co.uk/bread-cakes/401?s=20",
                "https://www.bestwaywholesale.co.uk/bread-cakes/401?s=40",
                "https://www.bestwaywholesale.co.uk/bread-cakes/401?s=60",
                "https://www.bestwaywholesale.co.uk/bread-cakes/401?s=80",
                "https://www.bestwaywholesale.co.uk/bread-cakes/401?s=100",
            ],
        )


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
