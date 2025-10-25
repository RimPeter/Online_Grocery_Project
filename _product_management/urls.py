from django.urls import path
from . import views


app_name = "_product_management"

urlpatterns = [
    path("", views.index, name="index"),
    path("dl/", views.dl_leaflet, name="dl"),
    path("qr.svg", views.qr_svg, name="qr"),
    path("dl.pdf", views.dl_leaflet_pdf, name="dl_pdf"),
    path("status/", views.leaflet_status, name="status"),
    path("active-orders/", views.active_orders, name="active_orders"),
    path("completed-orders/", views.completed_orders, name="completed_orders"),
    path("orders/<int:order_id>/complete/", views.mark_order_completed, name="mark_order_completed"),
    path("orders/complete-all/", views.mark_all_orders_completed, name="mark_all_orders_completed"),
    path("orders/<int:order_id>/activate/", views.mark_order_active, name="mark_order_active"),
    path("items-to-order/", views.items_to_order, name="items_to_order"),
    path("orders/<int:order_id>/delivery/", views.set_delivery_slot, name="set_delivery_slot"),
]
