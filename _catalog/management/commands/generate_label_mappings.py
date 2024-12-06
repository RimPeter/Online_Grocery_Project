# _catalog/management/commands/generate_label_mappings.py
#   python manage.py generate_label_mappings


import json
import os
from django.core.management.base import BaseCommand
from _catalog.models import All_Products, Product_Labels_For_Searchbar
from django.conf import settings
from collections import defaultdict

class Command(BaseCommand):
    help = 'Generate JSON files mapping labels to ga_product_ids and vice versa.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--output-dir',
            type=str,
            default=os.path.join(settings.BASE_DIR, 'label_mappings'),
            help='Directory where JSON files will be saved.',
        )
        parser.add_argument(
            '--labels-file',
            type=str,
            default='labels_to_ga_ids.json',
            help='Filename for labels to ga_product_ids mapping.',
        )
        parser.add_argument(
            '--products-file',
            type=str,
            default='ga_ids_to_labels.json',
            help='Filename for ga_product_ids to labels mapping.',
        )

    def handle(self, *args, **options):
        output_dir = options['output_dir']
        labels_file = options['labels_file']
        products_file = options['products_file']

        # Ensure the output directory exists
        os.makedirs(output_dir, exist_ok=True)

        # Initialize dictionaries
        labels_to_ga_ids = defaultdict(list)
        ga_ids_to_labels = {}

        self.stdout.write(self.style.NOTICE('Fetching Product Labels...'))

        # Fetch all Product_Labels_For_Searchbar entries with related All_Products
        # Using select_related to minimize database queries
        label_entries = Product_Labels_For_Searchbar.objects.select_related('product').all()

        total_entries = label_entries.count()
        self.stdout.write(self.style.NOTICE(f'Total label entries to process: {total_entries}'))

        for idx, entry in enumerate(label_entries, start=1):
            ga_product_id = entry.product.ga_product_id
            labels = entry.labels.split()  # Assuming labels are space-separated

            # Populate ga_ids_to_labels
            ga_ids_to_labels[ga_product_id] = labels

            # Populate labels_to_ga_ids
            for label in labels:
                labels_to_ga_ids[label].append(ga_product_id)

            # Provide progress feedback every 1000 entries
            if idx % 1000 == 0 or idx == total_entries:
                self.stdout.write(self.style.SUCCESS(f'Processed {idx}/{total_entries} entries.'))

        # Define file paths
        labels_to_ga_ids_path = os.path.join(output_dir, labels_file)
        ga_ids_to_labels_path = os.path.join(output_dir, products_file)

        self.stdout.write(self.style.NOTICE(f'Writing labels to ga_product_ids mapping to {labels_to_ga_ids_path}'))
        self.write_json_file(labels_to_ga_ids, labels_to_ga_ids_path)

        self.stdout.write(self.style.NOTICE(f'Writing ga_product_ids to labels mapping to {ga_ids_to_labels_path}'))
        self.write_json_file(ga_ids_to_labels, ga_ids_to_labels_path)

        self.stdout.write(self.style.SUCCESS('JSON files generated successfully.'))

    def write_json_file(self, data, file_path):
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                # Convert defaultdict to regular dict if necessary
                if isinstance(data, defaultdict):
                    data = dict(data)
                json.dump(data, f, ensure_ascii=False, indent=4)
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Failed to write {file_path}: {e}'))
