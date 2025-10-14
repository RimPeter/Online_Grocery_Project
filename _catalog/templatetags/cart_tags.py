from django import template
from _catalog.models import All_Products

register = template.Library()


@register.inclusion_tag('_catalog/partials/cart_dropdown.html', takes_context=True)
def cart_dropdown(context):
    request = context.get('request')
    items = []
    if not request:
        return {'items': items}
    cart = request.session.get('cart', {}) or {}
    if not cart:
        return {'items': items}
    # Fetch products in one query, preserve quantities
    ids = [int(pid) for pid in cart.keys() if str(pid).isdigit()]
    products = {p.id: p for p in All_Products.objects.filter(id__in=ids)}
    for pid_str, qty in cart.items():
        try:
            pid = int(pid_str)
        except Exception:
            continue
        prod = products.get(pid)
        if not prod:
            continue
        try:
            q = int(qty)
        except Exception:
            q = 1
        items.append({'product': prod, 'qty': q})
    return {'items': items}

