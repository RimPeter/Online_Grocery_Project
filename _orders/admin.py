# _orders/admin.py

from django.contrib import admin
from .models import Order, OrderItem

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0  # number of empty inlines to display

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'status', 'total', 'created_at')
    list_editable = ('status',)
    list_filter = ('user', 'created_at', 'status')
    action = ['mark_as_delivered']
    search_fields = ('user__username', 'user__email')
    
    def mark_as_delivered(self, request, queryset):
        updated = queryset.update(status='delivered')
        self.message_user(request, f"{updated} orders marked as delivered.")
    mark_as_delivered.short_description = "Mark selected orders as delivered"

@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ('supplier_completed', 'order', 'product', 'quantity', 'price')
    list_filter = ('supplier_completed', 'order__status',)
    actions = ['mark_as_completed']
    search_fields = ('order__id', 'product__product_name')
    
    def mark_as_completed(self, request, queryset):
        queryset.update(supplier_completed=True)
        self.message_user(request, "Selected items marked as completed.")
    mark_as_completed.short_description = "Mark selected items as completed"
    


