from django.urls import path
from . import views
from .views import product_list

urlpatterns = [
    path('', views.home, name='home'),
    path('products/', views.product_list, name='product_list'),
    path('product/<int:pk>/', views.product_detail, name='product_detail'),
    path('products/', product_list, name='product_list'),
]
