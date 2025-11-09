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
    # Allow up to GTIN-14 (and room for flexibility)
    retail_EAN = models.CharField(max_length=18, blank=True)

    # Product detail fields scraped from product pages
    description = models.TextField(blank=True)
    ingredients_nutrition = models.TextField(blank=True)
    other_info = models.TextField(blank=True)
    
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
        # Fallbacks: support '×' and uppercase 'X', and generic second-integer capture
        parts2 = re.split(r"\s*[xX×\-]\s*", s, maxsplit=2)
        if len(parts2) >= 2:
            m2 = re.search(r"\d+", parts2[1])
            if m2:
                try:
                    return int(m2.group(0))
                except ValueError:
                    pass
        nums = re.findall(r"\d+", s)
        if len(nums) >= 2:
            try:
                return int(nums[1])
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
    
    
class All_ProductsMissingRSP(All_Products):
    """Proxy for listing products with missing/invalid RSP in admin."""
    class Meta:
        proxy = True
        verbose_name = "Product with missing RSP"
        verbose_name_plural = "Products with missing RSP"


class HomeCategoryTile(models.Model):
    """Manual controls for which categories appear on the home page."""
    l1 = models.CharField(
        max_length=255,
        unique=True,
        help_text="Parent category (sub_category) name shown on home page.",
    )
    l2 = models.CharField(
        max_length=255,
        blank=True,
        help_text="(Legacy) optional child category name; ignored for main-category tiles.",
    )
    display_name = models.CharField(
        max_length=255,
        blank=True,
        help_text="Optional override for the label shown on the card.",
    )
    image_url = models.URLField(
        blank=True,
        help_text="Optional image URL; falls back to first product image if empty.",
    )
    is_active = models.BooleanField(default=True, db_index=True)
    sort_order = models.PositiveIntegerField(default=0, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('sort_order', 'l1', 'l2')
        verbose_name = "Home category tile"
        verbose_name_plural = "Home category tiles"

    def __str__(self):
        if self.l2:
            return f"{self.l1} → {self.l2}"
        return self.l1


class HomeValuePillar(models.Model):
    """Editable marketing blurbs shown on the home page."""
    key = models.CharField(
        max_length=50,
        unique=True,
        help_text="Stable identifier used for seeding defaults (e.g., 'speed').",
    )
    title = models.CharField(
        max_length=255,
        help_text="Short heading shown above the description.",
    )
    subtitle = models.CharField(
        max_length=255,
        help_text="Supporting sentence shown under the heading.",
    )
    sort_order = models.PositiveIntegerField(default=0, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('sort_order', 'id')
        verbose_name = "Home value pillar"
        verbose_name_plural = "Home value pillars"

    def __str__(self):
        return self.title
