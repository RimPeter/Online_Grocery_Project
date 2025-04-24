from django.contrib import admin
from .models import All_Products, Product_Labels_For_Searchbar
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