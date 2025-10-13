from django.contrib import admin
from .models import User, Address, Company, ContactMessage


admin.site.register(User)
admin.site.register(Address)

@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "phone", "city", "country", "is_default")
    list_filter = ("country", "is_default")
    search_fields = ("name", "legal_name", "email", "vat_number", "company_number", "city")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ("created_at", "user", "subject", "short_message")
    list_filter = ("created_at",)
    search_fields = ("subject", "message", "user__username", "user__email")
    ordering = ("-created_at",)

    def short_message(self, obj):
        text = obj.message or ""
        return (text[:60] + "…") if len(text) > 60 else text
    short_message.short_description = "Message"
