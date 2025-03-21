from django.urls import path
from .views import order_history_view
from . import views

urlpatterns = [
    path('history/', order_history_view, name='order_history'),
    path('delivery-slots/', views.delivery_slots_view, name='delivery_slots'),
    path('delete/<int:order_id>/', views.delete_order_view, name='order_delete'),
    path('order-summary/<int:order_id>/', views.order_summery_view, name='order_summery'),
]
