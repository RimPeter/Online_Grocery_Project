# _payments/views.py
import stripe
import logging
from django.shortcuts import render, redirect
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse
from django.urls import reverse
from decimal import Decimal, ROUND_HALF_UP
from _analytics.tracking import track_event
from _catalog.models import All_Products
from _orders.models import Order, OrderItem
from _orders.notifications import send_paid_order_notification
from _orders.pricing import (
    calculate_checkout_totals,
    calculate_session_cart_subtotal,
    resolve_customer_unit_price,
)
from .models import Payment

logger = logging.getLogger(__name__)


def _missing_checkout_profile_fields(user):
    required_fields = (
        ("username", "Username"),
        ("email", "Email"),
        ("first_name", "First name"),
        ("last_name", "Last name"),
        ("phone", "Phone"),
    )
    missing = []
    for attr, label in required_fields:
        value = getattr(user, attr, "")
        if not str(value or "").strip():
            missing.append(label)
    return missing


@login_required
def checkout_view(request, order_id):
    missing_profile_fields = _missing_checkout_profile_fields(request.user)
    if missing_profile_fields:
        missing_csv = ", ".join(missing_profile_fields)
        messages.error(
            request,
            f"Please complete and save your My Profile details before checkout. Missing: {missing_csv}.",
        )
        return redirect('profile')

    # Use the order_id provided by the URL to retrieve the order.
    try:
        order = Order.objects.get(id=order_id, user=request.user, status='pending')
    except Order.DoesNotExist:
        order = None

    # If no valid pending order is found via order_id, look for any pending order for this user.
    if not order:
        existing_order = Order.objects.filter(user=request.user, status='pending').first()
        if existing_order:
            order = existing_order

    # If there still isn’t a pending order, create a new one.
    if not order:
        cart = request.session.get('cart', {})
        if not cart:
            messages.error(request, "Your cart is empty. Please add items before checking out.")
            return redirect('cart_view')

        total_price = calculate_session_cart_subtotal(cart)
        product_ids = list(cart.keys())
        products = All_Products.objects.filter(pk__in=product_ids)

        order = Order.objects.create(
            user=request.user,
            total=total_price,
            status='pending'
        )

        for product in products:
            try:
                quantity = int(cart.get(str(product.pk), 0) or 0)
            except (TypeError, ValueError):
                quantity = 0
            if quantity <= 0:
                continue
            OrderItem.objects.create(
                order=order,
                product=product,
                quantity=quantity,
                price=resolve_customer_unit_price(product)
            )

    order_items = list(order.items.all())
    subtotal = sum(item.price * item.quantity for item in order_items)
    if order.total != subtotal:
        order.total = subtotal
        order.save(update_fields=['total'])

    pricing = calculate_checkout_totals(subtotal, has_items=bool(order_items))
    payable_total = pricing['grand_total']

    stripe_currency = (getattr(settings, "STRIPE_CURRENCY", "gbp") or "gbp").strip().lower()

    # Create or update Payment record
    payment, created = Payment.objects.get_or_create(
        user=request.user,
        order=order,
        defaults={
            'amount': payable_total,
            'currency': stripe_currency,
            'status': 'created',
        }
    )
    if not created:
        payment.amount = payable_total
        payment.currency = stripe_currency
        payment.save()

    # Calculate amount in cents (using proper rounding if needed)
    amount_in_cents = int((payable_total * Decimal('100')).quantize(Decimal('1'), rounding=ROUND_HALF_UP))

    # Optional: check if amount is below minimum
    if amount_in_cents < 50:
        messages.error(request, "Order total is too low to process payment. Please add more items.")
        return redirect('cart_view')

    stripe_secret_key = (settings.STRIPE_SECRET_KEY or "").strip()
    stripe_public_key = (settings.STRIPE_PUBLIC_KEY or "").strip()
    if not stripe_secret_key or not stripe_public_key:
        messages.error(
            request,
            "Stripe is not configured. Set STRIPE_PUBLIC_KEY and STRIPE_SECRET_KEY in your environment."
        )
        return redirect('order_summery', order_id=order.id)

    stripe.api_key = stripe_secret_key

    try:
        intent = stripe.PaymentIntent.create(
            amount=amount_in_cents,
            currency=stripe_currency,
            metadata={
                'payment_id': payment.id,
                'username': request.user.username,
            },
        )
    except stripe.error.StripeError as exc:
        logger.exception(
            "Stripe PaymentIntent.create failed for order_id=%s payment_id=%s",
            order.id,
            payment.id,
        )
        messages.error(request, f"Stripe error: {getattr(exc, 'user_message', str(exc))}")
        return redirect('order_summery', order_id=order.id)

    payment.stripe_payment_intent_id = intent['id']
    payment.save()

    success_url = request.build_absolute_uri(reverse('payment_success')) + f"?payment_id={payment.id}"

    context = {
        'clientSecret': intent['client_secret'],
        'STRIPE_PUBLIC_KEY': stripe_public_key,
        'payment': payment,
        'success_url': success_url,
        'order': order,
        'subtotal': subtotal,
        **pricing,
    }
    track_event(
        request,
        'checkout_started',
        value=payable_total,
        properties={
            'order_id': order.id,
            'items_count': len(order_items),
            'subtotal': str(subtotal),
            'delivery_charge': str(pricing['delivery_charge']),
            'discount_amount': str(pricing['basket_reward_discount']),
            'grand_total': str(payable_total),
        },
        path=reverse('checkout', args=[order.id]),
    )
    return render(request, '_payments/checkout.html', context)

def payment_success_view(request):
    payment_id = request.GET.get('payment_id')
    if not payment_id:
        messages.error(request, "No payment ID provided.")
        return redirect('order_history')

    try:
        payment = Payment.objects.get(id=payment_id, user=request.user)
    except Payment.DoesNotExist:
        messages.error(request, "Payment not found or not yours.")
        return redirect('order_history')

    order = payment.order
    if order and order.status == 'pending':
        order.status = 'paid'
        order.save()
        track_event(
            request,
            'paid_order',
            value=payment.amount,
            properties={
                'order_id': order.id,
                'payment_id': payment.id,
                'currency': payment.currency,
                'subtotal': str(order.total),
            },
            path=reverse('payment_success'),
        )
        for item in order.items.select_related('product'):
            track_event(
                request,
                'order_item_paid',
                label=item.product.name,
                value=item.quantity,
                properties={
                    'order_id': order.id,
                    'product_id': item.product_id,
                    'quantity': item.quantity,
                    'line_total': str(item.price * item.quantity),
                    'main_category': item.product.main_category,
                    'sub_category': item.product.sub_category,
                    'sub_subcategory': item.product.sub_subcategory,
                },
                path=reverse('payment_success'),
            )
        send_paid_order_notification(order)
        messages.success(request, f"Order #{order.id} is now paid.")
        if 'cart' in request.session:
            del request.session['cart']
    else:
        messages.info(request, "Order is not pending or does not exist.")

    return render(request, '_payments/payment_success.html')

def payment_cancel_view(request):
    messages.warning(request, "Payment canceled or failed.")
    return render(request, '_payments/payment_cancel.html')

def stripe_webhook_view(request):
    payload = request.body
    sig_header = request.META['HTTP_STRIPE_SIGNATURE']
    endpoint_secret = settings.STRIPE_WEBHOOK_SECRET

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, endpoint_secret
        )
    except stripe.error.SignatureVerificationError:
        return HttpResponse(status=400)

    if event['type'] == 'payment_intent.succeeded':
        payment_intent = event['data']['object']
        payment_id = payment_intent['metadata'].get('payment_id')

        if payment_id:
            try:
                payment = Payment.objects.get(id=payment_id)
                payment.status = 'succeeded'
                payment.save()

                order = payment.order  
                if order and order.status == 'pending':
                    order.status = 'paid'
                    order.save()
                if order and order.status == 'paid':
                    send_paid_order_notification(order)

            except Payment.DoesNotExist:
                pass

    return HttpResponse(status=200)

