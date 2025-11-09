from django.urls import path
from django.views.generic.base import RedirectView
from . import views


app_name = "_product_management"

urlpatterns = [
    path("", views.index, name="index"),
    path("dl/", views.dl_leaflet, name="dl"),
    path("qr.svg", views.qr_svg, name="qr"),
    path("dl.pdf", views.dl_leaflet_pdf, name="dl_pdf"),
    path("status/", views.leaflet_status, name="status"),
    path("pending-orders/", views.pending_orders, name="pending_orders"),
    path("paid-orders/", views.paid_orders, name="paid_orders"),
    path("processed-orders/", views.processed_orders, name="processed_orders"),
    # Backward-compat: redirect old path to new
    path("completed-orders/", RedirectView.as_view(pattern_name="_product_management:processed_orders", permanent=False)),
    path("delivered-orders/", views.delivered_orders, name="delivered_orders"),
    path("orders/<int:order_id>/complete/", views.mark_order_completed, name="mark_order_completed"),
    path("orders/complete-all/", views.mark_all_orders_completed, name="mark_all_orders_completed"),
    path("orders/<int:order_id>/activate/", views.mark_order_active, name="mark_order_active"),
    path("orders/<int:order_id>/paid/", views.mark_order_paid, name="mark_order_paid"),
    path("orders/<int:order_id>/process/", views.mark_order_processed, name="mark_order_processed"),
    path("items-to-order/", views.items_to_order, name="items_to_order"),
    path("items-to-order.pdf", views.items_to_order_pdf, name="items_to_order_pdf"),
    path("orders/<int:order_id>/delivery/", views.set_delivery_slot, name="set_delivery_slot"),
    path("commands/", views.commands, name="commands"),
    path("home-categories/", views.home_categories, name="home_categories"),
    path("missing-retail-ean/", views.missing_retail_ean, name="missing_retail_ean"),
]
