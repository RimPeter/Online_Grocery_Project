import logging
from decimal import Decimal

import stripe
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST, require_http_methods

from _accounts.referrals import ReferralError, attach_referral_code, can_attach_referral_code
from _orders.models import Order
from _analytics.tracking import track_event
from .models import Payment
from .services import (CheckoutError, prepare_checkout, get_payment_intent, process_webhook,
                       cancel_checkout, complete_zero_payment)

logger = logging.getLogger(__name__)


@login_required
@require_http_methods(['GET', 'POST'])
def checkout_view(request, order_id):
    order = get_object_or_404(Order, pk=order_id, user=request.user)
    if request.method == 'POST' and request.POST.get('apply_referral_code') is not None:
        if order.status != 'pending':
            messages.error(request, 'Cancel your current payment before changing referral discounts.')
        else:
            try:
                attach_referral_code(request.user, request.POST.get('referral_code', ''))
                messages.success(request, 'Referral code applied.')
            except ReferralError as exc:
                messages.error(request, str(exc))
        return redirect('checkout', order_id=order_id)
    if request.method == 'GET' and order.status == 'pending':
        # Viewing a page must not create payment attempts or freeze a basket.
        return render(request, '_payments/checkout_start.html', {'order': order,
            'can_add_referral_code': can_attach_referral_code(request.user)})
    if not settings.STRIPE_SECRET_KEY or not settings.STRIPE_PUBLIC_KEY:
        messages.error(request, 'Payments are temporarily unavailable. Please try again later.')
        return redirect('cart_view')
    try:
        was_pending = order.status == 'pending'
        order, payment = prepare_checkout(request.user, order_id, request.session.get('cart'))
        if was_pending:
            request.session.pop('cart', None)
            track_event(request, 'checkout_started', value=payment.amount,
                        properties={'order_id': order.pk, **order.checkout_snapshot['pricing']})
        if payment.amount == 0:
            complete_zero_payment(payment.pk)
            return redirect(reverse('payment_success') + f'?payment_id={payment.pk}')
        intent = get_payment_intent(payment.pk)
    except CheckoutError as exc:
        messages.error(request, str(exc))
        return redirect('cart_view')
    except stripe.error.StripeError:
        logger.exception('Stripe checkout failed for order %s', order_id)
        messages.error(request, 'Payment service unavailable. Your order is saved; retry or cancel below.')
        return render(request, '_payments/checkout_start.html', {'order': order, 'retry': True, 'payment': payment}, status=503)
    pricing = {key: Decimal(value) if isinstance(value, str) else value
               for key, value in order.checkout_snapshot['pricing'].items()}
    return render(request, '_payments/checkout.html', {
        'order': order, 'payment': payment, 'subtotal': order.total, **pricing,
        'clientSecret': intent['client_secret'], 'STRIPE_PUBLIC_KEY': settings.STRIPE_PUBLIC_KEY,
        'success_url': request.build_absolute_uri(reverse('payment_success')) + f'?payment_id={payment.pk}',
        'can_add_referral_code': False,
    })


@login_required
@require_GET
def payment_success_view(request):
    payment_id = request.GET.get('payment_id', '')
    if not payment_id.isdigit():
        return HttpResponse('Invalid payment ID.', status=400)
    payment = get_object_or_404(Payment.objects.select_related('order'), pk=payment_id, user=request.user)
    confirmed = payment.status == 'succeeded' and payment.order is not None and payment.order.status in ('paid', 'processed', 'delivered')
    return render(request, '_payments/payment_success.html', {'payment': payment, 'confirmed': confirmed})


@login_required
@require_POST
def payment_cancel_view(request):
    payment_id = request.POST.get('payment_id', '')
    if not payment_id.isdigit():
        return HttpResponse('Invalid payment ID.', status=400)
    payment = get_object_or_404(Payment, pk=payment_id, user=request.user)
    try:
        cancel_checkout(request.user, payment.pk)
        if not request.session.get('cart'):
            request.session['cart'] = {str(i.product_id): i.quantity for i in payment.order.items.all()}
        messages.success(request, 'Payment canceled. You can now change your basket.')
    except (CheckoutError, stripe.error.StripeError):
        messages.error(request, 'Could not cancel payment. It may already be processing; check its status before paying again.')
        return redirect(reverse('payment_success') + f'?payment_id={payment.pk}')
    return redirect('cart_view')


@csrf_exempt
@require_POST
def stripe_webhook_view(request):
    signature = request.META.get('HTTP_STRIPE_SIGNATURE', '')
    if not signature or not settings.STRIPE_WEBHOOK_SECRET:
        return HttpResponse(status=400)
    try:
        event = stripe.Webhook.construct_event(request.body, signature, settings.STRIPE_WEBHOOK_SECRET)
        process_webhook(event)
    except (ValueError, KeyError, TypeError, stripe.error.SignatureVerificationError):
        logger.warning('Rejected invalid Stripe webhook')
        return HttpResponse(status=400)
    return HttpResponse(status=200)
