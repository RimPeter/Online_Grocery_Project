from django.db import models
import re

# class Category(models.Model):
#     pass
    

# class Product(models.Model):
#     pass


class All_Products(models.Model):
    ga_product_id = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=255)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Split category into three levels
    main_category = models.CharField(max_length=255, blank=True)
    sub_category = models.CharField(max_length=255, blank=True)
    sub_subcategory = models.CharField(max_length=255, blank=True)
    
    variant = models.CharField(max_length=255, null=True, blank=True)
    list_position = models.PositiveIntegerField()
    url = models.URLField()
    image_url = models.URLField(null=True, blank=True, db_index=True)
    sku = models.CharField(max_length=50, null=True, blank=True)
    rsp = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    promotion_end_date = models.DateField(null=True, blank=True)
    multi_buy = models.BooleanField(default=False)
    retail_EAN = models.CharField(max_length=13, blank=True)
    
    # level1_category = models.CharField(max_length=255, blank=True)   # temp
    # level2_category = models.CharField(max_length=255, blank=True)   # temp
    # category        = models.CharField(max_length=255, blank=True)   # temp
    
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

    def pack_amount(self) -> int:
        """
        Extract the middle number from 'size x amount x cases' strings.
        Examples: '500g x 1 x 1', '1L x 6 x 1', '250ml×12×1'. Defaults to 1.
        """
        s = (self.variant or "").strip()
        if not s:
            return 1
        parts = re.split(r"\s*[x×]\s*", s, maxsplit=2)  # handles 'x' and '×'
        if len(parts) >= 2:
            m = re.search(r"\d+", parts[1])
            if m:
                try:
                    return int(m.group(0))
                except ValueError:
                    pass
        return 1

    @property
    def is_bulk(self) -> bool:
        return self.pack_amount() > 1 

    @property
    def bulk_total_price(self):
        """Total price for the full pack at RSP (rsp * pack_amount)."""
        if self.rsp is None:
            return None
        try:
            return self.rsp * self.pack_amount()
        except Exception:
            return None

    def __str__(self):
        return self.name

class Product_Labels_For_Searchbar(models.Model):
    product = models.ForeignKey(All_Products, on_delete=models.CASCADE, related_name='search_labels')
    labels = models.TextField(blank=True, help_text="Space-separated search labels derived from ga_product_id and category")

    def __str__(self):
        return f"Labels for {self.product.name}"
    
    
