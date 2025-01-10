import stripe
from django.shortcuts import render, redirect
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.urls import reverse

from _catalog.models import All_Products
from _orders.models import Order, OrderItem
from .models import Payment


@login_required
def checkout_view(request):
    # 1. Get user’s cart from session
    cart = request.session.get('cart', {})

    # 2. Compute total price
    total_price = 0
    if cart:
        product_ids = list(cart.keys())
        products = All_Products.objects.filter(pk__in=product_ids)
        for product in products:
            quantity = cart[str(product.pk)]
            total_price += product.price * quantity

    # 3. Create the Order in the database
    order = Order.objects.create(
        user=request.user,
        total=total_price,  # We can also store total at checkout
        # status='pending'  # if you have a status field
    )

    # 4. Create OrderItem records (line items) for that order
    for product in products:
        quantity = cart[str(product.pk)]
        OrderItem.objects.create(
            order=order,
            product=product,
            quantity=quantity,
            price=product.price
        )

    # 5. Initialize Stripe and create Payment & PaymentIntent
    stripe.api_key = settings.STRIPE_SECRET_KEY

    payment = Payment.objects.create(
        user=request.user,
        amount=total_price,
        currency='usd',
        status='created',
        # Optionally link Payment to the order if you like:
        # order=order,  # if Payment model has an order field
    )

    amount_in_cents = int(total_price * 100)

    intent = stripe.PaymentIntent.create(
        amount=amount_in_cents,
        currency='usd',
        metadata={
            'payment_id': payment.id,
            'username': request.user.username,
            # 'order_id': order.id,  # Could pass order ID if desired
        },
    )

    payment.stripe_payment_intent_id = intent['id']
    payment.save()

    # 6. Pass client secret to the template
    success_url = request.build_absolute_uri(reverse('payment_success'))
    context = {
        'clientSecret': intent['client_secret'],
        'STRIPE_PUBLIC_KEY': settings.STRIPE_PUBLIC_KEY,
        'payment': payment,
        'success_url': success_url,
    }
    return render(request, '_payments/checkout.html', context)

# payments/views.py (add these methods)
def payment_success_view(request):
    """
    A simple success page. 
    In a real scenario, confirm payment status with Stripe 
    or rely on webhooks to update your Payment model.
    """
    messages.success(request, "Payment successful!")
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
    except ValueError:
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError:
        return HttpResponse(status=400)

    if event['type'] == 'payment_intent.succeeded':
        payment_intent = event['data']['object']
        payment_id = payment_intent['metadata'].get('payment_id')
        # order_id = payment_intent['metadata'].get('order_id') # If you set it
        if payment_id:
            try:
                payment = Payment.objects.get(id=payment_id)
                payment.status = 'succeeded'
                payment.save()

                # If you have a link from Payment -> Order, mark the order as paid
                # payment.order.status = 'paid'
                # payment.order.save()

            except Payment.DoesNotExist:
                pass

    return HttpResponse(status=200)

