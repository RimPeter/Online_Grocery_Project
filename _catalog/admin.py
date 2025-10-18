from django.contrib import admin
from django.db.models import Q
from .models import All_Products, Product_Labels_For_Searchbar, All_ProductsMissingRSP
from django.utils.html import format_html

   
@admin.register(All_Products)
class All_ProductsAdmin(admin.ModelAdmin):
    list_display = ('name', 
                    'url', 
                    'image_link',
                    'image_url', 
                    'price', 
                    'main_category', 
                    'sub_category', 
                    'sub_subcategory',)
    
    list_filter = ('name', 'price')
    search_fields = ('name', 'sku')
    ordering = ('name',)

    @admin.display(description='Image')
    def image_link(self, obj):
        if obj.image_url:
            return format_html('<img src="{}" width="50" height="50" />', obj.image_url)
        return 'No image'
    

@admin.register(Product_Labels_For_Searchbar)
class ProductLabelsForSearchbarAdmin(admin.ModelAdmin):
    list_display = ('product', 'labels')
    search_fields = ('labels', 'product__name')


@admin.register(All_ProductsMissingRSP)
class MissingRSPAdmin(All_ProductsAdmin):
    """Admin view focused on items with missing/zero RSP so staff can fix."""
    list_display = (
        'name',
        'rsp',
        'price',
        'sku',
        'sub_category',
        'sub_subcategory',
        'image_link',
    )
    list_display_links = ('name',)
    list_editable = ('rsp',)
    search_fields = ('name', 'sku')
    list_filter = ('sub_category', 'sub_subcategory')
    ordering = ('name',)
    list_per_page = 50

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.filter(Q(rsp__isnull=True) | Q(rsp__lte=0))

    def has_add_permission(self, request):
        # This is for fixing existing entries, not creating new ones here
        return False
