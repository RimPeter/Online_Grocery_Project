from django.db import models
from _suppliers.models import Supplier

class Category(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField()
    parent_category = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True)
    
    def __str__(self):
        return self.name

class Product(models.Model):
    AVAILABILITY_STATUS_CHOICES = [
        ('in_stock', 'In Stock'),
        ('out_of_stock', 'Out of Stock'),
        ('pre_order', 'Pre-order'),
        ('discontinued', 'Discontinued'),
    ]

    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='products')
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name='products')
    name = models.CharField(max_length=255)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    unit = models.CharField(max_length=50)
    image = models.ImageField(upload_to='product_images/', null=True, blank=True)
    availability_status = models.CharField(
        max_length=20, choices=AVAILABILITY_STATUS_CHOICES, default='in_stock'
    )
    is_available = models.BooleanField(default=True)
    weight = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    requires_cooling = models.BooleanField(default=False)
    supplier_code = models.CharField(max_length=100)
    supplier_price = models.DecimalField(max_digits=10, decimal_places=2)
    min_order_quantity = models.PositiveIntegerField(default=1)
    lead_time_days = models.PositiveIntegerField()
    reorder_point = models.PositiveIntegerField()
    reorder_quantity = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    # Added __str__ method
    def __str__(self):
        return self.name

class Inventory(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='inventory')
    quantity_available = models.IntegerField()
    last_updated = models.DateTimeField(auto_now=True)
    expiry_date = models.DateField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.product.name} Inventory"
