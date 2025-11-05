import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from _catalog.models import All_Products


class Command(BaseCommand):
    help = "Import products from a plain JSON list (like products6.json) into All_Products."

    def add_arguments(self, parser):
        parser.add_argument(
            "json_path",
            nargs="?",
            default="products6.json",
            help="Path to JSON file (default: products6.json in the same app folder)",
        )
        parser.add_argument(
            "--update",
            action="store_true",
            help="Update existing products matched by ga_product_id instead of skipping.",
        )

    def handle(self, *args, **options):
        json_path = options["json_path"]

        # resolve relative to project root if needed
        path = Path(json_path)
        if not path.exists():
            # try to resolve relative to this management/commands folder
            here = Path(__file__).resolve().parent
            path = here / json_path
            if not path.exists():
                raise CommandError(f"JSON file not found at {json_path}")

        self.stdout.write(f"Loading products from {path} ...")

        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            raise CommandError("JSON must be a list of objects")

        created = 0
        updated = 0
        for obj in data:
            ga_id = obj.get("ga_product_id")
            if not ga_id:
                self.stderr.write("Skipping item without ga_product_id")
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

            try:
                if options["update"]:
                    obj_db, created_flag = All_Products.objects.update_or_create(
                        ga_product_id=ga_id,
                        defaults=defaults,
                    )
                    if created_flag:
                        created += 1
                    else:
                        updated += 1
                else:
                    # create only, skip if exists
                    All_Products.objects.get_or_create(
                        ga_product_id=ga_id,
                        defaults=defaults,
                    )
                    created += 1
            except Exception as e:
                self.stderr.write(f"Error creating {ga_id}: {e}")

        self.stdout.write(self.style.SUCCESS(f"Done. Created: {created}, Updated: {updated}"))
