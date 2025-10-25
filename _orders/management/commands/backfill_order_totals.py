from django.core.management.base import BaseCommand
from django.db.models import F, Sum, DecimalField, ExpressionWrapper
from _orders.models import Order


class Command(BaseCommand):
    help = 'Recalculate and backfill Order.total from OrderItem price x quantity.'

    def handle(self, *args, **options):
        amount_expr = ExpressionWrapper(
            F('items__price') * F('items__quantity'),
            output_field=DecimalField(max_digits=12, decimal_places=2),
        )
        updated = 0
        for order in Order.objects.all().iterator():
            total = order.items.aggregate(t=Sum(amount_expr)).get('t') or 0
            if order.total != total:
                order.total = total
                order.save(update_fields=['total'])
                updated += 1
        self.stdout.write(self.style.SUCCESS(f'Updated totals for {updated} order(s).'))

