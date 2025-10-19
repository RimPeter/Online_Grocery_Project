from django.core.management.base import BaseCommand
from django.db import transaction
import re

from _catalog.models import All_Products


PATTERN = re.compile(r"(?P<size>\d+\s*(?:ml|l|g|kg|s)?)\s*[xX×-]\s*(?P<pack>\d{1,3})")


class Command(BaseCommand):
    help = (
        "Backfill variant for products by parsing pack info from the name when missing. "
        "Example: '500ml x 12' or '52s × 12' -> variant set to 'size x pack'."
    )

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Do not write changes')
        parser.add_argument('--limit', type=int, default=0, help='Limit number of updates')

    def handle(self, *args, **opts):
        dry = opts['dry_run']
        limit = opts['limit']
        qs = All_Products.objects.filter(variant__isnull=True) | All_Products.objects.filter(variant='')
        updated = 0
        total = 0

        with transaction.atomic():
            for p in qs.iterator():
                total += 1
                m = PATTERN.search(p.name or '')
                if not m:
                    continue
                size = m.group('size').strip()
                pack = m.group('pack').strip()
                new_variant = f"{size} x {pack}"
                p.variant = new_variant
                updated += 1
                self.stdout.write(f"{p.id}: {p.name} -> {new_variant}")
                if not dry:
                    p.save(update_fields=['variant'])
                if limit and updated >= limit:
                    break

            if dry:
                transaction.set_rollback(True)

        self.stdout.write(self.style.SUCCESS(f"Scanned {total} products, updated {updated}."))

