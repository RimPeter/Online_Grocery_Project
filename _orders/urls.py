from django.urls import path
from .views import order_history_view, order_detail_view
from . import views

urlpatterns = [
    path('history/', order_history_view, name='order_history'),
    path('<int:order_id>/', order_detail_view, name='order_detail'),
    path('delivery-slots/', views.delivery_slots_view, name='delivery_slots'),
]
