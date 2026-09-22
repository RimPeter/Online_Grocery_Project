"""Persist a draft only on an explicit customer POST, under the checkout user lock."""
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.db import transaction
from _catalog.models import All_Products
from .models import Order, OrderItem
from .pricing import resolve_customer_unit_price


@transaction.atomic
def save_draft_cart(user, cart, order_id=None):
    get_user_model().objects.select_for_update().get(pk=user.pk)
    drafts = Order.objects.select_for_update().filter(user=user, status='pending')
    if order_id:
        order = drafts.filter(pk=order_id).first()
        if not order:
            raise ValueError('This order is no longer editable.')
    else:
        order = drafts.order_by('-created_at').first()
    if not isinstance(cart, dict) or not cart:
        raise ValueError('Your basket is empty.')
    quantities = {}
    try:
        for key, value in cart.items():
            product_id, quantity = int(key), int(value)
            if product_id <= 0 or not 1 <= quantity <= 999:
                raise ValueError
            quantities[product_id] = quantity
    except (TypeError, ValueError):
        raise ValueError('Your basket contains an invalid quantity.')
    products = list(All_Products.objects.filter(pk__in=quantities))
    if len(products) != len(quantities):
        raise ValueError('A product is no longer available. Review your basket.')
    lines = [(product, quantities[product.pk], resolve_customer_unit_price(product)) for product in products]
    if not order:
        order = Order.objects.create(user=user)
    order.items.all().delete()
    OrderItem.objects.bulk_create([OrderItem(order=order, product=p, quantity=q, price=price) for p, q, price in lines])
    order.total = sum((q * price for _, q, price in lines), Decimal('0.00'))
    from _accounts.referrals import build_referral_discounts
    from .pricing import calculate_checkout_totals
    base = calculate_checkout_totals(order.total)
    discounts = build_referral_discounts(user, order=order, pre_credit_total=base['pre_referral_total'])
    order.newcomer_referral_discount = discounts['newcomer_referral_discount']
    order.referral_credit_discount = discounts['referral_credit_discount']
    order.save(update_fields=['total', 'newcomer_referral_discount', 'referral_credit_discount'])
    return order
