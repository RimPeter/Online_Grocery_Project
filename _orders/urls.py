from django.urls import path
from .views import order_history_view, order_detail_view

urlpatterns = [
    path('history/', order_history_view, name='order_history'),
    path('<int:order_id>/', order_detail_view, name='order_detail'),
]
