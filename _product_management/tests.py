from collections import defaultdict
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory

from bs4 import BeautifulSoup
from django.contrib.auth import get_user_model
from django.core.management.base import CommandError
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from _catalog.models import All_Products
from _catalog.templatetags.price_tags import display_rsp
from _product_management.management.commands.generate_category_json import (
    Command as GenerateCategoryCommand,
)
from _product_management.management.commands.scrape_sub_subcategories import (
    Command as SubSubcategoryScraperCommand,
)
from _product_management.management.commands.scrape_subcategories import (
    Command as MainCategoryScraperCommand,
)
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

    def test_incomplete_categories_are_rejected_before_output_is_replaced(self):
        command = ProductScraperCommand()
        command.request_attempts = 10
        command.request_failures = 0

        with TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "products.json"
            output_path.write_text('[{"main_category": "Old"}]', encoding="utf-8")

            with self.assertRaisesMessage(CommandError, "missing main categories"):
                command._validate_scrape_result(
                    {
                        "Bread & Cakes": {},
                        "Beers, Wines & Spirits": {},
                    },
                    [{"main_category": "Bread and Cakes"}],
                    output_path,
                )

            self.assertEqual(
                output_path.read_text(encoding="utf-8"),
                '[{"main_category": "Old"}]',
            )

    def test_category_matching_ignores_ampersands_and_punctuation(self):
        self.assertEqual(
            ProductScraperCommand._category_key("Beers, Wines & Spirits"),
            ProductScraperCommand._category_key("Beers Wines and Spirits"),
        )

    def test_excessive_request_failures_are_rejected(self):
        command = ProductScraperCommand()
        command.request_attempts = 10
        command.request_failures = 3

        with TemporaryDirectory() as temp_dir:
            with self.assertRaisesMessage(CommandError, "failure rate"):
                command._validate_scrape_result(
                    {"Bread & Cakes": {}},
                    [{"main_category": "Bread and Cakes"}],
                    Path(temp_dir) / "products.json",
                )

    def test_large_product_count_drop_is_rejected(self):
        command = ProductScraperCommand()
        command.request_attempts = 10
        command.request_failures = 0

        with TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "products.json"
            output_path.write_text(
                "[" + ",".join('{"main_category":"Bread"}' for _ in range(8)) + "]",
                encoding="utf-8",
            )

            with self.assertRaisesMessage(CommandError, "previously"):
                command._validate_scrape_result(
                    {"Bread": {}},
                    [{"main_category": "Bread"} for _ in range(5)],
                    output_path,
                )


class CategoryTaxonomyTests(SimpleTestCase):
    def test_taxonomy_keeps_alcohol_navigation_without_product_rows(self):
        hierarchy = defaultdict(
            lambda: defaultdict(lambda: defaultdict(list))
        )
        taxonomy = {
            "Beers, Wines & Spirits": {
                "Beer": {
                    "Bottled Beer": "https://example.test/bottled-beer",
                    "Stout": "https://example.test/stout",
                },
                "Spirits & Fortified Wine": {
                    "Gin": "https://example.test/gin",
                },
            }
        }

        GenerateCategoryCommand._merge_taxonomy(hierarchy, taxonomy)

        self.assertIn("Beers, Wines & Spirits", hierarchy)
        self.assertEqual(
            set(hierarchy["Beers, Wines & Spirits"]["Beer"]),
            {"Bottled Beer", "Stout"},
        )
        self.assertEqual(
            hierarchy["Beers, Wines & Spirits"]["Beer"]["Stout"],
            [],
        )

    def test_product_label_wins_when_taxonomy_punctuation_differs(self):
        hierarchy = defaultdict(
            lambda: defaultdict(lambda: defaultdict(list))
        )
        hierarchy["Beers Wines and Spirits"]["Beer"]["Stout"].append("123")

        GenerateCategoryCommand._merge_taxonomy(
            hierarchy,
            {"Beers, Wines & Spirits": {"Beer": {"Stout": "ignored"}}},
        )

        self.assertEqual(list(hierarchy), ["Beers Wines and Spirits"])
        self.assertEqual(
            hierarchy["Beers Wines and Spirits"]["Beer"]["Stout"],
            ["123"],
        )


class CategoryScrapeSafetyTests(SimpleTestCase):
    def test_partial_main_category_discovery_is_rejected(self):
        with TemporaryDirectory() as temp_dir:
            with self.assertRaisesMessage(CommandError, "expected 2"):
                MainCategoryScraperCommand._validate_result(
                    ["bread-cakes", "beers-wines-spirits"],
                    {"Bread & Cakes": {"Bread": "https://example.test/bread"}},
                    Path(temp_dir) / "subcategories.json",
                    attempted_categories=2,
                    failed_categories=1,
                )

    def test_empty_subcategory_taxonomy_is_rejected(self):
        with TemporaryDirectory() as temp_dir:
            with self.assertRaisesMessage(CommandError, "incomplete"):
                SubSubcategoryScraperCommand._validate_result(
                    {"Beers, Wines & Spirits": {"Beer": "https://example.test"}},
                    {"Beers, Wines & Spirits": {"Beer": {}}},
                    Path(temp_dir) / "sub_subcategories.json",
                    request_attempts=1,
                    request_failures=0,
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
