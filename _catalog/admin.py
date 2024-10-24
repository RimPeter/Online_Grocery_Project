from django.contrib import admin
from .models import Inventory, Category, Product

admin.site.register(Inventory)
admin.site.register(Category)
admin.site.register(Product)

