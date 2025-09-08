from django.contrib import admin
from django.db.models import Count
from django.template.response import TemplateResponse
from django.urls import path
from .models import Order, OrderItem

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'status', 'total', 'created_at')
    list_editable = ('status',)
    list_filter = ('status', 'created_at')
    search_fields = ('id', 'user__username', 'user__email')
    date_hierarchy = 'created_at'
    ordering = ('-created_at',)
    actions = ['mark_as_delivered']       
    inlines = [OrderItemInline]           # <-- show items inline

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('user').annotate(items_count=Count('items'))

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                'all/',
                self.admin_site.admin_view(self.all_orders_view),
                name='orders_all',
            ),
        ]
        return custom + urls

    def all_orders_view(self, request):
        qs = (
            Order.objects
            .select_related('user')
            .annotate(items_count=Count('items'))
            .order_by('-created_at')
        )
        context = dict(
            self.admin_site.each_context(request),
            title='All Customer Orders',
            orders=qs,
            opts=self.model._meta,
        )
        return TemplateResponse(request, 'admin/_orders/all_orders.html', context)

    def mark_as_delivered(self, request, queryset):
        updated = queryset.update(status='delivered')
        self.message_user(request, f"{updated} orders marked as delivered.")
    mark_as_delivered.short_description = "Mark selected orders as delivered"


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ('supplier_completed', 'order', 'product', 'quantity', 'price')
    list_filter = ('supplier_completed', 'order__status',)
    actions = ['mark_as_completed']
    search_fields = ('order__id', 'product__name')   # <-- ensure correct field

    def mark_as_completed(self, request, queryset):
        queryset.update(supplier_completed=True)
        self.message_user(request, "Selected items marked as completed.")
    mark_as_completed.short_description = "Mark selected items as completed"
