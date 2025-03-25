from django.db import models
from django.conf import settings
from _catalog.models import All_Products
from django.db.models.signals import post_save
from django.dispatch import receiver

class Order(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('processed', 'Processed'),
        ('delivered', 'Delivered'),
        ('canceled', 'Canceled'),
    ]   
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE
    )
    created_at = models.DateTimeField(auto_now_add=True)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    delivery_date = models.DateField(null=True, blank=True)
    delivery_time = models.TimeField(null=True, blank=True)
 
    def __str__(self):
        return f"Order #{self.pk} (User: {self.user})"
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )

class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(All_Products, on_delete=models.CASCADE)
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
    order = instance.order
    # Are all items in this Order supplier_completed?
    all_completed = all(item.supplier_completed for item in order.items.all())
    if all_completed:
        # Update the order's status only if it's not already 'processed'
        if order.status != 'processed':
            order.status = 'processed'
            order.save()