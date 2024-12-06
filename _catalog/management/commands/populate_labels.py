#   python manage.py populate_labels

from django.core.management.base import BaseCommand
from _catalog.models import All_Products, Product_Labels_For_Searchbar
import os

class Command(BaseCommand):
    help = 'Populate the Product_Labels_For_Searchbar model with labels from All_Products, continuing from where it stopped.'

    def handle(self, *args, **options):
        processed_file = 'processed_ga_product_ids.txt'

        # Load already processed ga_product_ids if the file exists
        processed_ga_ids = set()
        if os.path.exists(processed_file):
            with open(processed_file, 'r') as f:
                for line in f:
                    processed_ga_ids.add(line.strip())

        # Retrieve products in a stable order (e.g., by ga_product_id)
        products = All_Products.objects.all().order_by('ga_product_id')
        total = products.count()
        self.stdout.write(self.style.NOTICE(f'Processing {total} products...'))
        self.stdout.write(self.style.NOTICE(f'Starting with {len(processed_ga_ids)} products already processed.'))

        count = len(processed_ga_ids)

        # Open the processed file in append mode so we can record progress
        with open(processed_file, 'a') as pf:
            for product in products:
                # If we've already processed this product, skip it
                if product.ga_product_id in processed_ga_ids:
                    continue

                # Generate labels
                name = product.name.split()
                category_words = product.category.split() if product.category else []
                all_words = set(name + category_words)
                labels_str = " ".join(all_words)

                # Update or create the associated labels record
                Product_Labels_For_Searchbar.objects.update_or_create(
                    product=product,
                    defaults={'labels': labels_str}
                )

                # Mark this product as processed
                pf.write(product.ga_product_id + '\n')
                pf.flush()  # ensure data is written to file immediately

                count += 1
                self.stdout.write(self.style.WARNING(f'Processed product {count}/{total} (ga_product_id: {product.ga_product_id})'))

        self.stdout.write(self.style.SUCCESS(f'Successfully populated labels for {count} products.'))
