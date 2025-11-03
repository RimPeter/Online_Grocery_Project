from django.core.management.base import BaseCommand
from _catalog.models import All_Products


class Command(BaseCommand):
    help = (
        "Preview dynamic home subcategories derived from All_Products. "
        "No database writes are performed (HomeSubcategory model removed)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--active",
            action="store_true",
            help="(Ignored) Kept for backward compatibility.",
        )
        parser.add_argument(
            "--reset",
            action="store_true",
            help="(Ignored) HomeSubcategory table no longer exists.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=24,
            help="Print up to this many preview entries (default 24).",
        )

    def handle(self, *args, **opts):
        if opts.get("reset"):
            self.stdout.write(self.style.WARNING(
                "--reset ignored: HomeSubcategory model was removed; using dynamic data."
            ))

        seen = set()
        preview = []
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
            seen.add(key)
            preview.append({
                'l1': l1,
                'l2': l2,
                'image_url': p.image_url or '',
            })

        # Sort and print a small preview to stdout so the command remains useful
        preview.sort(key=lambda x: (x['l1'].casefold(), x['l2'].casefold()))
        limit = int(opts.get('limit') or 24)
        to_show = preview[:max(0, limit)]

        for i, row in enumerate(to_show, start=1):
            self.stdout.write(f"{i:>2}. {row['l1']} -> {row['l2']} | {row['image_url']}")

        self.stdout.write(self.style.SUCCESS(
            f"Previewed {len(to_show)} of {len(preview)} dynamic home subcategories."
        ))
