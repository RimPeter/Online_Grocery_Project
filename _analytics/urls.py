from django.urls import path

from .views import visits_dashboard, visits_pages_summary, visits_summary

urlpatterns = [
    path('visits/dashboard/', visits_dashboard, name='visits_dashboard'),
    path('visits/', visits_summary, name='visits_summary'),
    path('visits/pages/', visits_pages_summary, name='visits_pages_summary'),
]
