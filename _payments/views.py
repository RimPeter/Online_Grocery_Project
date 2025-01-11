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
        status='pending'  # if you have a status field
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
        order=order,
        amount=total_price,
        currency='usd',
        status='created',
    )

    amount_in_cents = int(total_price * 100)

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

    # 6. Pass client secret to the template
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

