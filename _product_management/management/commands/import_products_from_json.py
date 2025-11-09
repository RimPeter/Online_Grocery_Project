import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from _catalog.models import All_Products


class Command(BaseCommand):
    help = "Import products from a plain JSON list into All_Products."

    def add_arguments(self, parser):
      # path to the json file
      parser.add_argument(
          "json_path",
          help="Path to JSON file (e.g. _product_management/management/commands/products6.json)",
      )
      # <-- THIS is the bit you don't have on Heroku yet
      parser.add_argument(
          "--update",
          action="store_true",
          help="Update existing products (matched by ga_product_id) instead of skipping.",
      )

    def handle(self, *args, **options):
        json_path = options["json_path"]
        do_update = options["update"]

        path = Path(json_path)
        if not path.exists():
            raise CommandError(f"JSON file not found at {json_path}")

        self.stdout.write(f"Loading products from {json_path} ...")

        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            raise CommandError("JSON must be a list of objects")

        created = 0
        updated = 0

        for obj in data:
            ga_id = obj.get("ga_product_id")
            if not ga_id:
                continue

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
                "promotion_end_date": obj.get("promotion_end_date"),
                "multi_buy": obj.get("multi_buy") or False,
                "retail_EAN": obj.get("retail_EAN") or "",
                "description": obj.get("description") or "",
                "ingredients_nutrition": obj.get("ingredients_nutrition") or "",
                "other_info": obj.get("other_info") or "",
                "vat_rate": obj.get("vat_rate") or "standard",
            }

            if do_update:
                # update-or-create path
                _, created_flag = All_Products.objects.update_or_create(
                    ga_product_id=ga_id,
                    defaults=defaults,
                )
                if created_flag:
                    created += 1
                else:
                    updated += 1
            else:
                # create-only path
                _, created_flag = All_Products.objects.get_or_create(
                    ga_product_id=ga_id,
                    defaults=defaults,
                )
                if created_flag:
                    created += 1

        self.stdout.write(self.style.SUCCESS(f"Done. Created: {created}, Updated: {updated}"))
