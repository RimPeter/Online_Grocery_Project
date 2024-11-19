from django.db import models

class Category(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='children'
    )

    class Meta:
        verbose_name_plural = 'Categories'

    def __str__(self):
        # Generate full category path (e.g., "Main Category > Subcategory > Sub-subcategory")
        ancestors = [self.name]
        parent = self.parent
        while parent is not None:
            ancestors.append(parent.name)
            parent = parent.parent
        return ' > '.join(reversed(ancestors))

    def get_level(self):
        # Returns the level of the category (1 for main, 2 for sub, etc.)
        level = 1
        parent = self.parent
        while parent is not None:
            level += 1
            parent = parent.parent
        return level

class Product(models.Model):
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='products')
    supplier = models.ForeignKey('_suppliers.Supplier', on_delete=models.CASCADE, related_name='products')
    name = models.CharField(max_length=255)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    unit = models.CharField(max_length=50)
    image = models.ImageField(upload_to='product_images/', null=True, blank=True)
    AVAILABILITY_STATUS_CHOICES = [
        ('in_stock', 'In Stock'),
        ('out_of_stock', 'Out of Stock'),
        ('pre_order', 'Pre-order'),
        ('discontinued', 'Discontinued'),
    ]
    availability_status = models.CharField(
        max_length=20,
        choices=AVAILABILITY_STATUS_CHOICES,
        default='in_stock'
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
    
    def __str__(self):
        return self.name
