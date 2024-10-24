from django.contrib import admin
from .models import Supplier, SupplierOrder, SupplierOrderItem

admin.site.register(Supplier)
admin.site.register(SupplierOrder)
admin.site.register(SupplierOrderItem)

