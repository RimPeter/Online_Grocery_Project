from django.urls import path

from .views import visits_dashboard, visits_summary

urlpatterns = [
    path('visits/dashboard/', visits_dashboard, name='visits_dashboard'),
    path('visits/', visits_summary, name='visits_summary'),
]
