# _payments/views.py
import stripe
from django.shortcuts import render, redirect
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse
from django.urls import reverse
from decimal import Decimal, ROUND_HALF_UP
from _catalog.models import All_Products
from _orders.models import Order, OrderItem
from .models import Payment

@login_required
def checkout_view(request, order_id):
    stripe.api_key = settings.STRIPE_SECRET_KEY

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

        total_price = 0
        product_ids = list(cart.keys())
        products = All_Products.objects.filter(pk__in=product_ids)
        for product in products:
            quantity = cart[str(product.pk)]
            total_price += product.price * quantity

        order = Order.objects.create(
            user=request.user,
            total=total_price,
            status='pending'
        )

        for product in products:
            quantity = cart[str(product.pk)]
            OrderItem.objects.create(
                order=order,
                product=product,
                quantity=quantity,
                price=product.price
            )

    # If the order total is zero, recalculate it from OrderItems.
    if order.total == 0:
        calculated_total = sum(item.price * item.quantity for item in order.items.all())
        order.total = calculated_total
        order.save()
        print(f"Recalculated order total: {order.total}")

    # Create or update Payment record
    payment, created = Payment.objects.get_or_create(
        user=request.user,
        order=order,
        defaults={
            'amount': order.total,
            'currency': 'usd',
            'status': 'created',
        }
    )
    if not created:
        payment.amount = order.total
        payment.save()

    # Calculate amount in cents (using proper rounding if needed)
    from decimal import Decimal, ROUND_HALF_UP
    amount_in_cents = int((order.total * Decimal('100')).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
    print(f"Order total: {order.total} | Amount in cents: {amount_in_cents}")

    # Optional: check if amount is below minimum
    if amount_in_cents < 50:
        messages.error(request, "Order total is too low to process payment. Please add more items.")
        return redirect('cart_view')

    intent = stripe.PaymentIntent.create(
        amount=amount_in_cents,
        currency='usd',
        metadata={
            'payment_id': payment.id,
            'username': request.user.username,
        },
    )
    payment.stripe_payment_intent_id = intent['id']
    payment.save()

    success_url = request.build_absolute_uri(reverse('payment_success')) + f"?payment_id={payment.id}"

    context = {
        'clientSecret': intent['client_secret'],
        'STRIPE_PUBLIC_KEY': settings.STRIPE_PUBLIC_KEY,
        'payment': payment,
        'success_url': success_url,
    }
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

            except Payment.DoesNotExist:
                pass

    return HttpResponse(status=200)

