"""
Custom Django management command to load products from JSON into the DB.
Usage:  python manage.py load_json_to_DB
"""

from django.core.management.base import BaseCommand
from django.conf import settings
from _catalog.models import All_Products

from datetime import datetime
from dateutil import parser
from pathlib import Path
import json


class Command(BaseCommand):
    help = "Loads products from a JSON file into the database."

    def handle(self, *args, **options):
        # Cross-platform path to data_job/products6.json
        data_path = Path(settings.BASE_DIR) / "data_job" / "products6.json"
        if not data_path.exists():
            raise FileNotFoundError(f"JSON file not found: {data_path}")

        with open(data_path, "r", encoding="utf-8") as file:
            data = json.load(file)

        # Date parser for optional promotion_end_date values
        def parse_date(date_str):
            try:
                parsed_date = parser.parse(date_str, dayfirst=True, fuzzy=True)
                if parsed_date.year != datetime.now().year:
                    parsed_date = parsed_date.replace(year=datetime.now().year)
                return parsed_date.date()
            except (ValueError, TypeError):
                return None

        # Upsert products
        created_count = 0
        updated_count = 0
        for product in data:
            try:
                promotion_end_date_str = product.get("promotion_end_date")
                promotion_end_date = (
                    parse_date(promotion_end_date_str) if promotion_end_date_str else None
                )

                obj, created = All_Products.objects.update_or_create(
                    ga_product_id=product["ga_product_id"],
                    defaults={
                        "name": product["name"],
                        "price": product.get("price", 0.0),
                        # Correct mapping of category fields
                        "main_category": product.get("main_category", ""),
                        "sub_category": product.get("sub_category", ""),
                        "sub_subcategory": product.get("sub_subcategory", ""),
                        "variant": product.get("variant"),
                        "list_position": product.get("list_position", 0),
                        "url": product.get("url", ""),
                        "image_url": product.get("image_url"),
                        "sku": product.get("sku"),
                        "rsp": product.get("rsp"),
                        "promotion_end_date": promotion_end_date,
                        "multi_buy": product.get("multi_buy", False),
                        "retail_EAN": product.get("retail_EAN", ""),
                        "vat_rate": product.get("vat_rate", "standard"),
                    },
                )
                if created:
                    created_count += 1
                    self.stdout.write(self.style.SUCCESS(f"Created {obj.ga_product_id}"))
                else:
                    updated_count += 1
                    self.stdout.write(f"Updated {obj.ga_product_id}")
            except Exception as e:
                self.stderr.write(
                    f"Error processing product {product.get('ga_product_id')}: {e}"
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"JSON load complete. Created: {created_count}, Updated: {updated_count}."
            )
        )

