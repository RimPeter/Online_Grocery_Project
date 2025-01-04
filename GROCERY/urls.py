from django.contrib import admin
from django.urls import path, include
from _accounts.views import custom_404_view


urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('_catalog.urls')),
    path('accounts/', include('_accounts.urls')),
    path('payments/', include('_payments.urls')),
]

handler404 = custom_404_view
