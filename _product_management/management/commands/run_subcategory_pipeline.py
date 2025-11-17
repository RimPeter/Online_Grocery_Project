"""
Run the full Bestway subcategory scraping pipeline in one go.

This command runs, in order:
    python manage.py scrape_subcategories
    python manage.py scrape_sub_subcategories
    python manage.py scraper_for_sub_subcategory
    python manage.py load_sub_subcategory_products

Usage:
    python manage.py run_subcategory_pipeline
"""

from django.core.management import BaseCommand, call_command


class Command(BaseCommand):
    help = (
        "Run the full Bestway subcategory scraping pipeline and load "
        "results into All_Products."
    )

    def handle(self, *args, **options):
        """
        Execute the four underlying management commands in sequence.
        """
        verbosity = options.get("verbosity", 1)

        steps = [
            "scrape_subcategories",
            "scrape_sub_subcategories",
            "scraper_for_sub_subcategory",
            "load_sub_subcategory_products",
        ]

        for name in steps:
            self.stdout.write(self.style.NOTICE(f"Running {name}..."))
            call_command(name, verbosity=verbosity)

        self.stdout.write(
            self.style.SUCCESS("Subcategory scraping pipeline completed.")
        )

