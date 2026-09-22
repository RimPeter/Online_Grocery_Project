from django.db import transaction
from .models import Order


@transaction.atomic
def advance_fulfilment(order_id, target):
    order = Order.objects.select_for_update().get(pk=order_id)
    allowed = {'processed': 'paid', 'delivered': 'processed'}
    if allowed.get(target) != order.status:
        return False
    order.status = target
    order.save(update_fields=['status'])
    return True
