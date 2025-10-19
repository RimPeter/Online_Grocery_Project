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
                    'variant',
                    'main_category', 
                    'sub_category', 
                    'sub_subcategory',)
    
    list_filter = ('name', 'price', 'sub_category')
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


class BulkListFilter(admin.SimpleListFilter):
    title = 'bulk'
    parameter_name = 'bulk'

    def lookups(self, request, model_admin):
        return (
            ('yes', 'Bulk items'),
            ('no', 'Single items'),
        )

    def queryset(self, request, queryset):
        val = self.value()
        if val == 'yes':
            # Heuristic: variant contains an x/× followed by a number >= 2
            return queryset.filter(variant__iregex=r'[xX×-]\s*[2-9]\d*')
        if val == 'no':
            return queryset.exclude(variant__iregex=r'[xX×-]\s*[2-9]\d*')
        return queryset

# Re-register All_Products with Bulk filter added
All_ProductsAdmin.list_filter = All_ProductsAdmin.list_filter + (BulkListFilter,)
