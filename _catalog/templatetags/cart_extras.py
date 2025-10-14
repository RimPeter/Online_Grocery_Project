from django import template

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

