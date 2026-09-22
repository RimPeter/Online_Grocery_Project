"""Checkout and payment lifecycle. Lock user, then order, then payment consistently."""
from datetime import timedelta
from decimal import Decimal

import stripe
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from _accounts.models import Address, Company
from _accounts.referrals import build_referral_discounts, finalize_referral_rewards
from _catalog.models import CategoryNodeSetting
from _orders.models import Order
from _orders.notifications import send_paid_order_notification
from _orders.pricing import calculate_checkout_totals
from _product_management.models import DeliverySlotSettings, BasketPricingSettings
from _product_management.rsp import calculate_rsp_from_cost
from .models import Payment, WebhookEvent
from _analytics.models import AnalyticsEvent


class CheckoutError(ValueError):
    pass


def money_to_minor(amount):
    return int(Decimal(str(amount)) * 100)


@transaction.atomic
def prepare_checkout(user, order_id, cart=None):
    # NO KEY UPDATE still serializes this customer's checkout, while allowing
    # another customer's referral reward to reference this user on PostgreSQL.
    user = get_user_model().objects.select_for_update(no_key=True).get(pk=user.pk)
    order = Order.objects.select_for_update().filter(pk=order_id, user=user).first()
    if not order:
        raise CheckoutError('Order not found. Open your basket to start checkout.')
    if order.status == 'awaiting_payment':
        payment = Payment.objects.filter(order=order).order_by('-id').first()
        if not payment or order.snapshot_needs_review or order.checkout_snapshot.get('version') != 1:
            raise CheckoutError('This payment needs review. Please contact support.')
        return order, payment
    if order.status != 'pending':
        raise CheckoutError('This order is no longer available for checkout.')
    if Order.objects.filter(user=user, status='awaiting_payment').exists():
        raise CheckoutError('Complete or cancel your existing payment before starting another checkout.')
    if any(not str(getattr(user, field, '') or '').strip() for field in
           ('username', 'email', 'first_name', 'last_name', 'phone')):
        raise CheckoutError('Complete your profile before checkout.')
    address = Address.objects.filter(user=user).order_by('-is_default', 'id').first()
    if not address or any(not str(getattr(address, field, '') or '').strip() for field in
                          ('street_address', 'house_number', 'city', 'postal_code')):
        raise CheckoutError('Add a complete delivery address before checkout.')
    slots = DeliverySlotSettings.get_solo()
    today = timezone.localdate()
    if (not order.delivery_date or not order.delivery_time
            or not today + timedelta(days=slots.effective_min_days_ahead()) <= order.delivery_date
            <= today + timedelta(days=slots.effective_max_days_ahead())
            or order.delivery_time.strftime('%H:%M') not in {s['value'] for s in slots.build_time_slot_options()}):
        raise CheckoutError('Choose a valid delivery slot before checkout.')
    items = list(order.items.select_related('product').order_by('id'))
    if not items:
        raise CheckoutError('Your basket is empty.')
    if cart is not None and cart != {str(i.product_id): i.quantity for i in items}:
        raise CheckoutError('Your basket has changed. Review it before checkout.')
    hidden = list(CategoryNodeSetting.objects.filter(is_visible_to_customers=False))
    pricing_config = BasketPricingSettings.get_solo()
    subtotal = Decimal('0.00')
    for item in items:
        product = item.product
        hidden_category = any(all(not getattr(node, field) or getattr(node, field) == getattr(product, field)
                                  for field in ('main_category', 'sub_category', 'sub_subcategory')) for node in hidden)
        price = calculate_rsp_from_cost(product.price, multiplier=pricing_config.rsp_multiplier)
        if (not product.is_visible_to_customers or hidden_category
                or price <= 0 or price > 50 or not 1 <= item.quantity <= 999):
            raise CheckoutError(f'{product.name} is unavailable or has an invalid quantity.')
        if item.price != price:
            raise CheckoutError('Prices have changed. Review your basket before checkout.')
        subtotal += price * item.quantity
    pricing_settings = {key: getattr(pricing_config, key) for key in
                        ('minimum_order_total', 'delivery_charge', 'discount_threshold', 'discount_amount')}
    if subtotal < pricing_settings['minimum_order_total']:
        raise CheckoutError(f"Minimum order is £{pricing_settings['minimum_order_total']:.2f}.")
    base = calculate_checkout_totals(subtotal, pricing_settings=pricing_settings)
    discounts = build_referral_discounts(user, order=order, pre_credit_total=base['pre_referral_total'])
    pricing = calculate_checkout_totals(subtotal, pricing_settings=pricing_settings,
        newcomer_referral_discount=discounts['newcomer_referral_discount'],
        referral_credit_discount=discounts['referral_credit_discount'])
    if 0 < pricing['grand_total'] < Decimal('0.50'):
        # Leave enough payable for Stripe rather than reserving unusable credit.
        credit = max(Decimal('0'), pricing['referral_credit_discount'] - (Decimal('0.50') - pricing['grand_total']))
        pricing = calculate_checkout_totals(subtotal, pricing_settings=pricing_settings,
            newcomer_referral_discount=discounts['newcomer_referral_discount'], referral_credit_discount=credit)
    if 0 < pricing['grand_total'] < Decimal('0.50'):
        raise CheckoutError('The payable amount must be zero or at least £0.50. Please review your basket.')
    for item in items:
        item.product_name = item.product.name
        item.product_sku = item.product.sku or ''
        item.vat_rate_snapshot = item.product.vat_rate
        item.save(update_fields=['product_name', 'product_sku', 'vat_rate_snapshot'])
    company = Company.get_default()
    company_fields = ('name', 'legal_name', 'address_line1', 'address_line2', 'city', 'region',
                      'postal_code', 'country', 'vat_number', 'company_number', 'email', 'phone',
                      'website', 'currency_code', 'invoice_footer')
    order.checkout_snapshot = {
        'version': 1,
        'pricing': {key: str(value) if isinstance(value, Decimal) else value for key, value in pricing.items()},
        'address': {field: getattr(address, field) for field in ('street_address', 'house_number',
                    'apartment', 'city', 'postal_code', 'delivery_instructions')},
        'customer': {'name': user.get_full_name() or user.username, 'email': user.email, 'phone': user.phone},
        'company': {field: getattr(company, field) for field in company_fields} if company else {},
        'delivery_date': order.delivery_date.isoformat(), 'delivery_time': order.delivery_time.isoformat(),
        'currency': settings.STRIPE_CURRENCY,
    }
    order.total = subtotal
    order.newcomer_referral_discount = pricing['newcomer_referral_discount']
    order.referral_credit_discount = pricing['referral_credit_discount']
    order.status = 'awaiting_payment'
    order.save()
    payment = Payment.objects.create(user=user, order=order, amount=pricing['grand_total'], currency=settings.STRIPE_CURRENCY)
    return order, payment


@transaction.atomic
def get_payment_intent(payment_id):
    # Serializes refreshes; the persistent key also covers a timeout after Stripe creates the intent.
    order_id = Payment.objects.values_list('order_id', flat=True).get(pk=payment_id)
    order = Order.objects.select_for_update().get(pk=order_id)
    payment = Payment.objects.select_for_update().get(pk=payment_id)
    if order.status != 'awaiting_payment' or payment.status in ('succeeded', 'canceled'):
        raise CheckoutError('This payment is no longer active.')
    if payment.stripe_payment_intent_id:
        return stripe.PaymentIntent.retrieve(payment.stripe_payment_intent_id, api_key=settings.STRIPE_SECRET_KEY)
    intent = stripe.PaymentIntent.create(
        amount=money_to_minor(payment.amount), currency=payment.currency,
        metadata={'payment_id': str(payment.pk), 'order_id': str(payment.order_id)},
        idempotency_key=str(payment.attempt_key), api_key=settings.STRIPE_SECRET_KEY)
    payment.stripe_payment_intent_id = intent['id']
    payment.save(update_fields=['stripe_payment_intent_id', 'updated_at'])
    return intent


def _complete(order, payment):
    if payment.status == 'succeeded':
        return
    if order.status != 'awaiting_payment' or not order.checkout_snapshot:
        raise CheckoutError('Order is not awaiting this payment.')
    if Decimal(order.checkout_snapshot['pricing']['grand_total']) != payment.amount:
        raise CheckoutError('Frozen order total does not match payment.')
    order.status = 'paid'
    order.save(update_fields=['status'])
    payment.status = 'succeeded'
    payment.save(update_fields=['status', 'updated_at'])
    finalize_referral_rewards(order)
    checkout_event = AnalyticsEvent.objects.filter(event_type='checkout_started', properties__order_id=order.pk).order_by('-pk').first()
    event_defaults = {'user_id': order.user_id, 'visit_id': checkout_event.visit_id if checkout_event else None,
                      'session_key': checkout_event.session_key if checkout_event else '', 'path': '/payments/stripe-webhook/'}
    AnalyticsEvent.objects.create(**event_defaults, event_type='paid_order', value=payment.amount,
        properties={'order_id': order.pk, 'payment_id': payment.pk, 'currency': payment.currency})
    for item in order.items.select_related('product'):
        AnalyticsEvent.objects.create(**event_defaults, event_type='order_item_paid', label=item.display_name,
            value=item.quantity, properties={'order_id': order.pk, 'product_id': item.product_id,
                'quantity': item.quantity, 'line_total': str(item.price * item.quantity),
                'main_category': item.product.main_category, 'sub_category': item.product.sub_category,
                'sub_subcategory': item.product.sub_subcategory})
    transaction.on_commit(lambda: send_paid_order_notification(order))


@transaction.atomic
def complete_zero_payment(payment_id):
    original = Payment.objects.get(pk=payment_id)
    get_user_model().objects.select_for_update(no_key=True).get(pk=original.user_id)
    order = Order.objects.select_for_update().get(pk=original.order_id)
    payment = Payment.objects.select_for_update().get(pk=payment_id)
    if payment.amount != 0:
        raise CheckoutError('Payment is required.')
    _complete(order, payment)


@transaction.atomic
def process_webhook(event):
    event_type = event.get('type')
    if event_type not in ('payment_intent.succeeded', 'payment_intent.canceled', 'payment_intent.payment_failed'):
        return
    intent = event['data']['object']
    payment_id = intent.get('metadata', {}).get('payment_id')
    if not payment_id:
        return  # Another integration on the same Stripe account.
    original = Payment.objects.filter(pk=payment_id).first()
    if not original or not original.order_id:
        raise CheckoutError('Unknown payment.')
    if original.user_id:
        get_user_model().objects.select_for_update(no_key=True).get(pk=original.user_id)
    order = Order.objects.select_for_update().get(pk=original.order_id)
    payment = Payment.objects.select_for_update().get(pk=original.pk)
    if (intent.get('id') != payment.stripe_payment_intent_id
            or intent.get('currency') != payment.currency
            or intent.get('amount') != money_to_minor(payment.amount)):
        raise CheckoutError('Payment identity or amount mismatch.')
    if event_type == 'payment_intent.succeeded' and (
            intent.get('status') != 'succeeded'
            or intent.get('amount_received') != money_to_minor(payment.amount)):
        raise CheckoutError('Payment has not been fully received.')
    if event_type == 'payment_intent.canceled' and intent.get('status') != 'canceled':
        raise CheckoutError('Payment is not canceled.')
    _, created = WebhookEvent.objects.get_or_create(stripe_event_id=event['id'])
    if not created or payment.status == 'succeeded':
        return
    if event_type == 'payment_intent.succeeded':
        _complete(order, payment)
    elif event_type == 'payment_intent.canceled' and order.status == 'awaiting_payment':
        payment.status = 'canceled'
        payment.save(update_fields=['status', 'updated_at'])
        order.status = 'canceled'
        order.save(update_fields=['status'])
    # A failed attempt can retry the same intent; keep its order/credit reserved.


@transaction.atomic
def cancel_checkout(user, payment_id):
    get_user_model().objects.select_for_update(no_key=True).get(pk=user.pk)
    original = Payment.objects.get(pk=payment_id, user=user)
    order = Order.objects.select_for_update().get(pk=original.order_id)
    payment = Payment.objects.select_for_update().get(pk=payment_id)
    if order.status != 'awaiting_payment':
        raise CheckoutError('This payment can no longer be canceled.')
    if not payment.stripe_payment_intent_id and payment.amount:
        # Recover a potentially created intent after an earlier network timeout.
        get_payment_intent(payment.pk)
        payment.refresh_from_db()
    if payment.stripe_payment_intent_id:
        intent = stripe.PaymentIntent.cancel(payment.stripe_payment_intent_id, api_key=settings.STRIPE_SECRET_KEY)
        if intent['status'] != 'canceled':
            raise CheckoutError('Payment is processing. Wait for confirmation before trying again.')
    payment.status = 'canceled'
    payment.save(update_fields=['status', 'updated_at'])
    order.status = 'canceled'
    order.save(update_fields=['status'])
