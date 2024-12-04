from django.contrib import admin
from django.urls import path
import _catalog
from django.urls import include


urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('_catalog.urls')),
]
