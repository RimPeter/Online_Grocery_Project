from django.contrib import admin
from .models import Supplier

@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = (
        'company_name', 
        'company_id', 
        'contact_person', 
        'email', 
        'phone', 
        'city', 
        'is_active', 
        'created_at'
    )
    list_filter = ('is_active', 'city')
    search_fields = ('company_name', 'company_id', 'contact_person', 'email', 'phone')
    ordering = ('company_name',)