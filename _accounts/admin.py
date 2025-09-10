from django.contrib import admin
from .models import User, Address, Company


admin.site.register(User)
admin.site.register(Address)

@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "phone", "city", "country", "is_default")
    list_filter = ("country", "is_default")
    search_fields = ("name", "legal_name", "email", "vat_number", "company_number", "city")
    prepopulated_fields = {"slug": ("name",)}