from django.urls import path
from . import views


app_name = "_leaflet_creator"

urlpatterns = [
    path("", views.index, name="index"),
    path("dl/", views.dl_leaflet, name="dl"),
    path("qr.svg", views.qr_svg, name="qr"),
]
