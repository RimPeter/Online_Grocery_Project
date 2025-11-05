# Usage: Generate a JSON file from product categories
#    python manage.py generate_category_json


from django.core.management.base import BaseCommand
from _catalog.models import All_Products
import json
from collections import defaultdict

class Command(BaseCommand):
    help = 'Generate a JSON file from product categories'

    def handle(self, *args, **kwargs):
        # Initialize the nested dictionary structure
        category_hierarchy = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))

        # Fetch all products
        all_products = All_Products.objects.all()

        # Build the hierarchy
        for product in all_products:
            category_parts = product.category.split(' > ')
            if len(category_parts) < 3:
                self.stdout.write(f"Skipping invalid category: {product.category}")
                continue

            level1, level2, level3 = category_parts
            ga_product_id = product.ga_product_id

            # Append the product ID to the appropriate Level 3 category
            category_hierarchy[level1][level2][level3].append(ga_product_id)

        # Convert the defaultdict to a standard dictionary for JSON serialization
        result = {}
        for level1, level2_dict in category_hierarchy.items():
            result[level1] = [
                {level2: [{level3: product_ids} for level3, product_ids in level3_dict.items()]}
                for level2, level3_dict in level2_dict.items()
            ]

        # Write to JSON file
        output_file = 'category_structure.json'
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=4, ensure_ascii=False)

        self.stdout.write(self.style.SUCCESS(f"JSON file successfully generated at: {output_file}"))
