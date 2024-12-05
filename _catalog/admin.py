from django.contrib import admin
from .models import All_Products
from django.utils.html import format_html

#admin.site.register(Product)

# @admin.register(Category)
# class CategoryAdmin(admin.ModelAdmin):
#     list_display = ('parent', 'name', 'get_level')
#     ordering = ('parent',) 
    
# @admin.register(Product)
# class ProductAdmin(admin.ModelAdmin):
#     list_display = ('name', 'image_link', 'category', 'supplier', 'rsp', 'por')
#     list_filter = ('category', 'supplier')
#     search_fields = ('name', 'about_product', 'description', 'ingredients')
#     ordering = ('name',)
    
#     @admin.display(description='Image')
#     def image_link(self, obj):
#         if obj.image:
#             return format_html('<img src="{}" width="50" height="50" />', obj.image)
#         else:
#             return 'No image'
        
@admin.register(All_Products)
class All_ProductsAdmin(admin.ModelAdmin):
    list_display = ('name', 'url', 'image_link', 'price')
    list_filter = ('name', 'price')
    search_fields = ('name', 'sku')
    ordering = ('name',)

    @admin.display(description='Image')
    def image_link(self, obj):
        if obj.image_url:
            return format_html('<img src="{}" width="50" height="50" />', obj.image_url)
        return 'No image'