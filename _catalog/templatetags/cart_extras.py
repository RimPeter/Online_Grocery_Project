from django import template
from decimal import Decimal
from _catalog.models import All_Products
from _orders.pricing import calculate_checkout_totals

register = template.Library()


@register.simple_tag(takes_context=True)
def cart_count(context):
    request = context.get('request')
    if not request:
        return 0
    cart = request.session.get('cart', {})
    try:
        return sum(int(q) for q in cart.values())
    except Exception:
        return 0


@register.simple_tag(takes_context=True)
def cart_total_value(context):
    request = context.get('request')
    if not request:
        return Decimal('0.00')

    cart = request.session.get('cart', {}) or {}
    if not isinstance(cart, dict) or not cart:
        return Decimal('0.00')

    ids = [int(pid) for pid in cart.keys() if str(pid).isdigit()]
    if not ids:
        return Decimal('0.00')

    products = {p.id: p for p in All_Products.objects.filter(id__in=ids)}
    total = Decimal('0.00')

    for pid_str, qty in cart.items():
        try:
            pid = int(pid_str)
            quantity = int(qty)
        except Exception:
            continue
        if quantity <= 0:
            continue

        product = products.get(pid)
        if not product:
            continue

        base_unit = product.rsp if (product.rsp is not None and product.rsp > 0) else product.price
        try:
            unit_price = Decimal(str(base_unit))
        except Exception:
            continue

        try:
            pack = int(product.pack_amount()) if callable(product.pack_amount) else int(getattr(product, 'pack_amount', 1) or 1)
        except Exception:
            pack = 1

        if pack > 1:
            unit_price *= Decimal(pack)

        total += unit_price * quantity

    pricing = calculate_checkout_totals(total, has_items=total > 0)
    return pricing['grand_total']
