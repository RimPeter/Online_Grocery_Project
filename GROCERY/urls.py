from django.contrib import admin
from django.urls import path, include
from django.views.generic.base import RedirectView
from django.conf import settings
from django.conf.urls.static import static
from django.templatetags.static import static as static_static
from _accounts.views import custom_404_view


urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('_catalog.urls')),
    path('accounts/', include('_accounts.urls')),
    path('payments/', include('_payments.urls')),
    path('orders/', include('_orders.urls')),
    path('leaflet/', include('_product_management.urls')),
    # Redirect browsers that request /favicon.ico to the static SVG
    path('favicon.ico', RedirectView.as_view(url=static_static('images/favicon.svg'), permanent=True)),
    
]

handler404 = custom_404_view

# Serve company logos folder in development
if getattr(settings, 'DEBUG', True):
    import os
    urlpatterns += static('/company_logos/', document_root=os.path.join(settings.BASE_DIR, 'company_logos'))
