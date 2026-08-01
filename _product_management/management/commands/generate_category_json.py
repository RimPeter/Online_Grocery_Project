# Usage: Generate a JSON file from product categories
#    python manage.py generate_category_json


from django.core.management.base import BaseCommand
from django.conf import settings
import json
import re
from collections import defaultdict
from pathlib import Path


class Command(BaseCommand):
    help = 'Generate a JSON file from sub_subcategory_products.json into category_structure.json'

    @staticmethod
    def _category_key(value):
        """Return a punctuation-insensitive key for matching taxonomy labels."""
        text = (value or "").replace("&", " and ").casefold()
        return " ".join(re.findall(r"[a-z0-9]+", text))

    @classmethod
    def _matching_name(cls, names, candidate):
        candidate_key = cls._category_key(candidate)
        for name in names:
            if cls._category_key(name) == candidate_key:
                return name
        return candidate

    @classmethod
    def _merge_taxonomy(cls, hierarchy, taxonomy):
        """
        Keep known navigation nodes even when a product feed is incomplete.

        Product-backed labels win when punctuation differs, so a future feed
        using "Beers Wines and Spirits" will not create a duplicate group for
        the taxonomy label "Beers, Wines & Spirits".
        """
        if not isinstance(taxonomy, dict):
            return

        for taxonomy_main, taxonomy_subcats in taxonomy.items():
            if not isinstance(taxonomy_subcats, dict):
                continue
            main_name = cls._matching_name(hierarchy.keys(), taxonomy_main)
            main_bucket = hierarchy[main_name]

            for taxonomy_subcat, taxonomy_leaves in taxonomy_subcats.items():
                subcat_name = cls._matching_name(
                    main_bucket.keys(), taxonomy_subcat
                )
                leaf_bucket = main_bucket[subcat_name]
                if not isinstance(taxonomy_leaves, dict):
                    continue
                for taxonomy_leaf in taxonomy_leaves.keys():
                    leaf_name = cls._matching_name(
                        leaf_bucket.keys(), taxonomy_leaf
                    )
                    leaf_bucket[leaf_name]

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

        # Navigation taxonomy is independent from the latest product import.
        # Merging it prevents a temporarily incomplete feed from removing an
        # entire category from the storefront while keeping product ID lists
        # empty until authorised product data is available.
        taxonomy_path = source_path.with_name("sub_subcategories.json")
        if taxonomy_path.exists():
            try:
                taxonomy = json.loads(taxonomy_path.read_text(encoding="utf-8"))
                self._merge_taxonomy(category_hierarchy, taxonomy)
            except Exception as exc:
                self.stderr.write(
                    self.style.WARNING(
                        f"Could not merge navigation taxonomy from "
                        f"{taxonomy_path}: {exc}"
                    )
                )

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
