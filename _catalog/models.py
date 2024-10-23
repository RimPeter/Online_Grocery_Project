from django.db import models
from _suppliers.models import Supplier

class Category(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField()
    parent_category = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True)

class Product(models.Model):
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='products')
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name='products')
    name = models.CharField(max_length=255)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    unit = models.CharField(max_length=50)
    image_url = models.URLField()
    availability_status = models.CharField(max_length=50)
    is_available = models.BooleanField(default=True)
    weight = models.DecimalField(max_digits=10, decimal_places=2)
    requires_cooling = models.BooleanField(default=False)
    supplier_code = models.CharField(max_length=100)
    supplier_price = models.DecimalField(max_digits=10, decimal_places=2)
    min_order_quantity = models.IntegerField()
    lead_time_days = models.IntegerField()
    reorder_point = models.IntegerField()
    reorder_quantity = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class Inventory(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='inventory')
    quantity_available = models.IntegerField()
    last_updated = models.DateTimeField(auto_now=True)
    expiry_date = models.DateField(null=True, blank=True)
