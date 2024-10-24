from django.db import models
from _catalog.models import Product

class Supplier(models.Model):
    name = models.CharField(max_length=255)
    company_id = models.CharField(max_length=100, unique=True)
    contact_person = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=15)
    address = models.TextField()
    city = models.CharField(max_length=50)
    postal_code = models.CharField(max_length=20)
    website = models.URLField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    bank_account = models.CharField(max_length=100)
    tax_number = models.CharField(max_length=100)
    rating = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    lead_time_days = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name
    
class SupplierOrder(models.Model):
    STATUS_CHOICES = [
        ('ordered', 'Ordered'),
        ('shipped', 'Shipped'),
        ('received', 'Received'),
        ('canceled', 'Canceled'),
    ]

    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name='orders')
    order_date = models.DateTimeField(auto_now_add=True)
    expected_delivery = models.DateField()
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='ordered'
    )
    notes = models.TextField(null=True, blank=True)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"Supplier Order {self.id} to {self.supplier.name}"

class SupplierOrderItem(models.Model):
    supplier_order = models.ForeignKey(SupplierOrder, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.product.name} x {self.quantity}"


