from django.contrib import admin
from django.urls import path, include


urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('_catalog.urls')),
    path('accounts/', include('_accounts.urls')),
]
