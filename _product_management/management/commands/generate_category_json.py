# Usage: Generate a JSON file from product categories
#    python manage.py generate_category_json


from django.core.management.base import BaseCommand
from django.conf import settings
import json
from collections import defaultdict
from pathlib import Path


class Command(BaseCommand):
    help = 'Generate a JSON file from sub_subcategory_products.json into category_structure.json'

    def handle(self, *args, **kwargs):
        base_dir = Path(settings.BASE_DIR)
        source_path = (
            base_dir
            / "_product_management"
            / "management"
            / "commands"
            / "sub_subcategory_products.json"
        )

        if not source_path.exists():
            self.stderr.write(
                self.style.ERROR(f"Source file not found: {source_path}")
            )
            return

        try:
            raw = source_path.read_text(encoding="utf-8")
            data = json.loads(raw)
        except Exception as exc:
            self.stderr.write(
                self.style.ERROR(f"Failed to read/parse {source_path}: {exc}")
            )
            return

        if not isinstance(data, list):
            self.stderr.write(
                self.style.ERROR("Expected a list of product objects in sub_subcategory_products.json")
            )
            return

        # Build hierarchy: main_category -> sub_category -> sub_subcategory -> [ga_product_id,...]
        category_hierarchy = defaultdict(
            lambda: defaultdict(lambda: defaultdict(list))
        )

        for obj in data:
            try:
                level1 = (obj.get("main_category") or "").strip()
                level2 = (obj.get("sub_category") or "").strip()
                level3 = (obj.get("sub_subcategory") or "").strip()
                ga_id = (obj.get("ga_product_id") or "").strip()
            except AttributeError:
                continue

            if not (level1 and level2 and level3 and ga_id):
                # Skip incomplete rows; they don't help the structure.
                continue

            category_hierarchy[level1][level2][level3].append(ga_id)

        # Convert to the existing category_structure.json shape:
        # {
        #   "Level1": [
        #     { "Level2": [
        #         { "Level3": ["ga_id1", "ga_id2", ...] },
        #         ...
        #     ]},
        #     ...
        #   ],
        #   ...
        # }
        result = {}
        for level1, level2_dict in category_hierarchy.items():
            level2_list = []
            for level2, level3_dict in level2_dict.items():
                level3_list = []
                for level3, product_ids in level3_dict.items():
                    # Ensure deterministic ordering of IDs
                    sorted_ids = sorted(product_ids)
                    level3_list.append({level3: sorted_ids})
                # Sort Level3 entries by key for stable output
                level3_list.sort(key=lambda d: next(iter(d.keys())).casefold())
                level2_list.append({level2: level3_list})
            # Sort Level2 entries by key for stable output
            level2_list.sort(key=lambda d: next(iter(d.keys())).casefold())
            result[level1] = level2_list

        output_path = (
            base_dir
            / "_product_management"
            / "management"
            / "commands"
            / "category_structure.json"
        )
        output_path.write_text(
            json.dumps(result, indent=4, ensure_ascii=False),
            encoding="utf-8",
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"category_structure.json successfully generated at: {output_path}"
            )
        )
