from django.urls import path
from . import views

urlpatterns = [
    path('checkout/', views.checkout_view, name='checkout'),
    path('payment-success/', views.payment_success_view, name='payment_success'),
    path('payment-cancel/', views.payment_cancel_view, name='payment_cancel'),
    path('stripe-webhook/', views.stripe_webhook_view, name='stripe_webhook'),
]
