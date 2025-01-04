import stripe
from django.shortcuts import render, redirect
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from _catalog.models import All_Products
from .models import Payment
from django.urls import reverse

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

    # Convert to cents if using USD (Stripe expects amounts in cents for USD)
    amount_in_cents = int(total_price * 100)

    # 3. Create Payment record in our database
    payment = Payment.objects.create(
        user=request.user,
        amount=total_price,
        currency='usd',
        status='created',
    )

    # 4. Initialize Stripe with secret key
    stripe.api_key = settings.STRIPE_SECRET_KEY

    # 5. Create PaymentIntent on Stripe
    intent = stripe.PaymentIntent.create(
        amount=amount_in_cents,
        currency='usd',
        metadata={
            'payment_id': payment.id,
            'username': request.user.username
        },
    )

    # 6. Update our Payment object with the Stripe PaymentIntent ID
    payment.stripe_payment_intent_id = intent['id']
    payment.save()

    # 7. Pass client secret to the template
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
        # Invalid payload
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError:
        # Invalid signature
        return HttpResponse(status=400)

    # Handle the event
    if event['type'] == 'payment_intent.succeeded':
        payment_intent = event['data']['object']
        payment_id = payment_intent['metadata'].get('payment_id')
        if payment_id:
            try:
                payment = Payment.objects.get(id=payment_id)
                payment.status = 'succeeded'
                payment.save()
            except Payment.DoesNotExist:
                pass

    elif event['type'] == 'payment_intent.payment_failed':
        payment_intent = event['data']['object']
        payment_id = payment_intent['metadata'].get('payment_id')
        if payment_id:
            try:
                payment = Payment.objects.get(id=payment_id)
                payment.status = 'failed'
                payment.save()
            except Payment.DoesNotExist:
                pass

    return HttpResponse(status=200)


