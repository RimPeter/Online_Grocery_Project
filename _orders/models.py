from django.db import models, transaction
from django.conf import settings
from _catalog.models import All_Products
from django.db.models.signals import post_save, post_delete, pre_delete
from django.core.exceptions import ValidationError
from django.dispatch import receiver
from django.db.models import Sum, F, DecimalField, ExpressionWrapper

class Order(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('awaiting_payment', 'Awaiting payment'),
        ('paid', 'Paid'),
        ('processed', 'Processed'),
        ('delivered', 'Delivered'),
        ('canceled', 'Canceled'),
    ]   
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    newcomer_referral_discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    referral_credit_discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    checkout_snapshot = models.JSONField(default=dict, blank=True)
    snapshot_needs_review = models.BooleanField(default=False)

    delivery_date = models.DateField(null=True, blank=True)
    delivery_time = models.TimeField(null=True, blank=True)

    @transaction.atomic
    def save(self, *args, **kwargs):
        previous = type(self).objects.select_for_update().filter(pk=self.pk).first() if self.pk else None
        if previous and previous.status != self.status:
            transitions = {'pending': {'awaiting_payment', 'canceled'}, 'awaiting_payment': {'paid', 'canceled'},
                           'paid': {'processed'}, 'processed': {'delivered'}, 'delivered': set(), 'canceled': set()}
            if self.status not in transitions.get(previous.status, set()):
                raise ValidationError('Invalid order status transition.')
        if previous and previous.status != 'pending':
            frozen_fields = ('total', 'newcomer_referral_discount', 'referral_credit_discount',
                             'checkout_snapshot', 'delivery_date', 'delivery_time')
            fields = kwargs.get('update_fields')
            if any((not fields or name in fields) and getattr(self, name) != getattr(previous, name)
                   for name in frozen_fields):
                raise ValidationError('Order details are fixed after checkout starts.')
        super().save(*args, **kwargs)
 
    def __str__(self):
        return f"Order #{self.pk} (User: {self.user})"
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )

class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(All_Products, on_delete=models.PROTECT)
    product_name = models.CharField(max_length=255, blank=True)
    product_sku = models.CharField(max_length=50, blank=True)
    vat_rate_snapshot = models.CharField(max_length=10, blank=True)

    @property
    def display_name(self):
        return self.product_name or self.product.name

    @transaction.atomic
    def save(self, *args, **kwargs):
        current_order = Order.objects.select_for_update().get(pk=self.order_id)
        previous = type(self).objects.select_related('order').filter(pk=self.pk).first() if self.pk else None
        if current_order.status != 'pending' or (previous and previous.order.status != 'pending'):
            fields = ('order_id', 'product_id', 'quantity', 'price', 'product_name', 'product_sku', 'vat_rate_snapshot')
            if not previous or any(getattr(self, field) != getattr(previous, field) for field in fields):
                raise ValidationError('Purchased order items cannot be changed.')
        super().save(*args, **kwargs)
    quantity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)

    supplier_completed = models.BooleanField(
        default=False,
        help_text="Mark if we've already ordered this item from suppliers."
    )

    def __str__(self):
        return f"Order #{self.order_id} | {self.product.name} x {self.quantity}"
    
    
@receiver(post_save, sender=OrderItem)
def set_order_status_processed_if_all_completed(sender, instance, **kwargs):
    """
    Whenever an OrderItem is saved (e.g., marking supplier_completed=True),
    check if *all* items in that order are supplier_completed.
    If so, set order.status = 'processed'.
    """
    order = Order.objects.get(pk=instance.order_id)
    # Are all items in this Order supplier_completed?
    all_completed = all(item.supplier_completed for item in order.items.all())
    if all_completed:
        # Update the order's status only if it's not already 'processed'
        if order.status == 'paid':
            order.status = 'processed'
            order.save()


def _recalc_order_total(order: Order):
    if order.status != 'pending':
        return
    try:
        amount_expr = ExpressionWrapper(F('price') * F('quantity'), output_field=DecimalField(max_digits=12, decimal_places=2))
        total = order.items.aggregate(total=Sum(amount_expr)).get('total') or 0
        if order.total != total:
            order.total = total
            order.save(update_fields=['total'])
    except Exception:
        # Best-effort; avoid breaking save cycles if something goes wrong
        pass


@receiver(post_save, sender=OrderItem)
def recalc_total_on_item_save(sender, instance, **kwargs):
    _recalc_order_total(instance.order)


@receiver(post_delete, sender=OrderItem)
def recalc_total_on_item_delete(sender, instance, **kwargs):
    _recalc_order_total(instance.order)


@receiver(pre_delete, sender=Order)
def protect_completed_order(sender, instance, **kwargs):
    current = Order.objects.select_for_update().get(pk=instance.pk)
    if current.status != 'pending' or instance.payment_set.exists():
        raise ValidationError('Orders with payment history cannot be deleted.')


@receiver(pre_delete, sender=OrderItem)
def protect_purchased_item(sender, instance, **kwargs):
    if Order.objects.select_for_update().get(pk=instance.order_id).status != 'pending':
        raise ValidationError('Purchased order items cannot be deleted.')
