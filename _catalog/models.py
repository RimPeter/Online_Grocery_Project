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
        ordering = ['name']

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
    about_product = models.CharField(max_length=255, blank=True)
    rsp = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    por = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    pack_size = models.CharField(max_length=10, blank=True)
    product_code = models.CharField(max_length=10, blank=True)
    retail_EAN = models.CharField(max_length=13, blank=True)
    VAT_RATE_CHOICES = [
        ('standard', 'Standard'),
        ('reduced', 'Reduced'),
        ('zero', 'Zero'),
    ]
    vat_rate = models.CharField(
        max_length=10,
        choices=VAT_RATE_CHOICES,
        default='standard'
    )
    brand = models.CharField(max_length=35, blank=True)
    image = models.URLField(max_length=500, null=True, blank=True)
    description = models.TextField()
    ingredients = models.TextField(blank=True)
    other_information = models.TextField(blank=True)
    unit = models.CharField(max_length=50)
    
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
    requires_cooling = models.BooleanField(default=False)
    supplier_code = models.CharField(max_length=100)
    supplier_price = models.DecimalField(max_digits=10, decimal_places=2)
    min_order_quantity = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.name
