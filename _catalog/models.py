from django.db import models

class Category(models.Model):
    pass
    

class Product(models.Model):
    pass


class All_Products(models.Model):
    ga_product_id = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=255)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    category = models.CharField(max_length=255)
    variant = models.CharField(max_length=255, null=True, blank=True)
    list_position = models.PositiveIntegerField()
    url = models.URLField()
    image_url = models.URLField(null=True, blank=True)
    sku = models.CharField(max_length=50, null=True, blank=True)
    rsp = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    promotion_end_date = models.DateField(null=True, blank=True)
    multi_buy = models.BooleanField(default=False)
    retail_EAN = models.CharField(max_length=13, blank=True)
    VAT_RATE_CHOICES = [
        ('standard', 'Standard'),
        ('reduced', 'Reduced'),
        ('zero', 'Zero'),
        ('exempt', 'Exempt'),
    ]
    vat_rate = models.CharField(
        max_length=10,
        choices=VAT_RATE_CHOICES,
        default='standard'
    )

    def __str__(self):
        return self.name

class Product_Labels_For_Searchbar(models.Model):
    product = models.ForeignKey(All_Products, on_delete=models.CASCADE, related_name='search_labels')
    labels = models.TextField(blank=True, help_text="Space-separated search labels derived from ga_product_id and category")

    def __str__(self):
        return f"Labels for {self.product.name}"
    
    