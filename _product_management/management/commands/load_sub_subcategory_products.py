"""
Load products from sub_subcategory_products.json into All_Products.

Usage:
    python manage.py load_sub_subcategory_products
    python manage.py load_sub_subcategory_products --json-path path/to/file.json

By default this command looks for:
    _product_management/management/commands/sub_subcategory_products.json
relative to settings.BASE_DIR.
"""

import json
from datetime import datetime
from pathlib import Path

from dateutil import parser
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from _catalog.models import All_Products


class Command(BaseCommand):
    help = (
        "Load products from sub_subcategory_products.json into the "
        "All_Products table."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--json-path",
            type=str,
            help=(
                "Optional explicit path to JSON file. "
                "If omitted, uses "
                "_product_management/management/commands/"
                "sub_subcategory_products.json under BASE_DIR."
            ),
        )

    def handle(self, *args, **options):
        json_arg = options.get("json_path")

        if json_arg:
            data_path = Path(json_arg)
        else:
            data_path = (
                Path(settings.BASE_DIR)
                / "_product_management"
                / "management"
                / "commands"
                / "sub_subcategory_products.json"
            )

        if not data_path.exists():
            raise CommandError(f"JSON file not found at {data_path}")

        self.stdout.write(f"Loading products from {data_path} ...")

        try:
            raw = data_path.read_text(encoding="utf-8")
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise CommandError(f"Failed to parse JSON: {exc}") from exc

        if not isinstance(data, list):
            raise CommandError("JSON must be a list of objects")

        def parse_date(date_str):
            """Best-effort parse of promotion_end_date strings."""
            if not date_str:
                return None
            try:
                parsed = parser.parse(date_str, dayfirst=True, fuzzy=True)
                # Normalise year to current if site omits it
                if parsed.year != datetime.now().year:
                    parsed = parsed.replace(year=datetime.now().year)
                return parsed.date()
            except (ValueError, TypeError):
                return None

        created = 0
        updated = 0

        for obj in data:
            ga_id = obj.get("ga_product_id")
            if not ga_id:
                continue

            promo_raw = obj.get("promotion_end_date")
            promo_date = parse_date(promo_raw) if promo_raw else None

            defaults = {
                "name": obj.get("name") or "",
                "price": obj.get("price") or 0,
                "main_category": obj.get("main_category") or "",
                "sub_category": obj.get("sub_category") or "",
                "sub_subcategory": obj.get("sub_subcategory") or "",
                "variant": obj.get("variant") or "",
                "list_position": obj.get("list_position") or 0,
                "url": obj.get("url") or "",
                "image_url": obj.get("image_url") or "",
                "sku": obj.get("sku") or "",
                "rsp": obj.get("rsp"),
                "promotion_end_date": promo_date,
                "multi_buy": obj.get("multi_buy") or False,
                "retail_EAN": obj.get("retail_EAN") or "",
                "description": obj.get("description") or "",
                "ingredients_nutrition": obj.get("ingredients_nutrition") or "",
                "other_info": obj.get("other_info") or "",
                "vat_rate": obj.get("vat_rate") or "standard",
            }

            try:
                _, was_created = All_Products.objects.update_or_create(
                    ga_product_id=ga_id,
                    defaults=defaults,
                )
            except Exception as exc:
                self.stderr.write(
                    f"Error saving product {ga_id!r}: {exc}"
                )
                continue

            if was_created:
                created += 1
                self.stdout.write(self.style.SUCCESS(f"Created {ga_id}"))
            else:
                updated += 1
                self.stdout.write(f"Updated {ga_id}")

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. Created: {created}, Updated: {updated}."
            )
        )

