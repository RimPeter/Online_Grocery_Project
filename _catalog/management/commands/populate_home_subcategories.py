from django.core.management.base import BaseCommand
from _catalog.models import All_Products, HomeSubcategory


class Command(BaseCommand):
    help = "Populate HomeSubcategory with one entry per unique subcategory using a representative product image."

    def add_arguments(self, parser):
        parser.add_argument(
            "--active",
            action="store_true",
            help="Mark created entries as active",
        )
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete existing HomeSubcategory rows before populating",
        )

    def handle(self, *args, **opts):
        if opts.get("reset"):
            count = HomeSubcategory.objects.count()
            HomeSubcategory.objects.all().delete()
            self.stdout.write(self.style.WARNING(f"Cleared {count} existing HomeSubcategory rows."))

        created = 0
        seen = set()
        qs = (
            All_Products.objects
            .exclude(image_url__isnull=True)
            .exclude(image_url='')
            .exclude(image_url='/img/products/no-image.png')
            .order_by('sub_category', 'sub_subcategory', 'id')
        )
        for p in qs.iterator():
            l1 = (p.sub_category or '').strip() or 'Other'
            l2 = (p.sub_subcategory or '').strip() or 'Other'
            key = (l1.casefold(), l2.casefold())
            if key in seen:
                continue
            obj, was_created = HomeSubcategory.objects.get_or_create(
                l1=l1, l2=l2,
                defaults={
                    'display_name': l2,
                    'image_url': p.image_url or '',
                    'active': bool(opts.get('active')),
                    'sort_order': created,
                }
            )
            seen.add(key)
            if was_created:
                created += 1

        self.stdout.write(self.style.SUCCESS(f"Created {created} HomeSubcategory rows."))
