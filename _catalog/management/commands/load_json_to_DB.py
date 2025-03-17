# This file is a custom Django management command that loads products from a JSON file into the database.
#   python manage.py load_json_to_DB

from django.core.management.base import BaseCommand
from _catalog.models import All_Products
from datetime import datetime
from dateutil import parser
import json

class Command(BaseCommand):
    help = 'Loads products from a JSON file into the database.'

    def handle(self, *args, **options):
        # Load JSON data from the file
        with open('data_job\products6.json', 'r', encoding='utf-8') as file:
            data = json.load(file)

        # Define a function to parse dates
        def parse_date(date_str):
            try:
                # Parse the date using dateutil.parser
                parsed_date = parser.parse(date_str, dayfirst=True, fuzzy=True)
                # Replace the year with the current year if necessary
                if parsed_date.year != datetime.now().year:
                    parsed_date = parsed_date.replace(year=datetime.now().year)
                return parsed_date.date()
            except (ValueError, TypeError):
                # If parsing fails, return None
                return None

        # Loop through each product in the data
        for product in data:
            try:
                # Parse the promotion_end_date
                promotion_end_date_str = product.get("promotion_end_date", None)
                if promotion_end_date_str:
                    promotion_end_date = parse_date(promotion_end_date_str)
                else:
                    promotion_end_date = None

                # Update existing product or create a new one
                obj, created = All_Products.objects.update_or_create(
                    ga_product_id=product["ga_product_id"],
                    defaults={
                        "name": product["name"],
                        "price": product.get("price", 0.0),
                        "category": product.get("category", "Unknown"),
                        "variant": product.get("variant", None),
                        "list_position": product.get("list_position", 0),
                        "url": product.get("url", ""),
                        "image_url": product.get("image_url", None),
                        "sku": product.get("sku", None),
                        "rsp": product.get("rsp", None),
                        "promotion_end_date": promotion_end_date,
                        "multi_buy": product.get("multi_buy", False),
                        "retail_EAN": product.get("retail_EAN", ""),
                        "vat_rate": product.get("vat_rate", "standard"),
                    }
                )
                if created:
                    self.stdout.write(self.style.SUCCESS(f"Product {product['ga_product_id']} created."))
                else:
                    self.stdout.write(f"Product {product['ga_product_id']} updated.")
            except Exception as e:
                self.stderr.write(f"Error processing product {product.get('ga_product_id')}: {e}")

        self.stdout.write(self.style.SUCCESS("JSON data has been successfully loaded into the database."))
