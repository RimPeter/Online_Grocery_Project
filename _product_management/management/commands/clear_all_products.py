
# This file is part of the Django project.
# python manage.py clear_all_products

from django.core.management.base import BaseCommand
from _catalog.models import All_Products

class Command(BaseCommand):
    help = "Delete every row in the All_Products table."

    def handle(self, *args, **options):
        count, _ = All_Products.objects.all().delete()
        self.stdout.write(self.style.SUCCESS(f"Deleted {count} All_Products rows."))
