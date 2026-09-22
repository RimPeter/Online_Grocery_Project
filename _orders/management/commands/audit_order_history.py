from django.core.management.base import BaseCommand
from _orders.models import Order


class Command(BaseCommand):
    help = 'List legacy orders requiring verified invoice data; never rewrites transaction history.'

    def handle(self, *args, **options):
        for order in Order.objects.filter(snapshot_needs_review=True).order_by('pk'):
            amount = order.checkout_snapshot.get('recorded_paid_total', 'unknown')
            self.stdout.write(f'order={order.pk} status={order.status} recorded_paid_total={amount} needs_review=True')
