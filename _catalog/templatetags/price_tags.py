from django import template
from decimal import Decimal, InvalidOperation
from _product_management.rsp import calculate_rsp_from_cost

register = template.Library()


def _to_decimal(val):
    try:
        if val is None:
            return None
        return Decimal(str(val))
    except (InvalidOperation, ValueError, TypeError):
        return None


@register.filter
def display_rsp(product):
    """Return the global display unit price for a product."""
    if not product:
        return Decimal('0.00')

    base_price = _to_decimal(getattr(product, 'price', None))
    if base_price is not None:
        try:
            derived_rsp = calculate_rsp_from_cost(base_price)
            if derived_rsp is not None:
                return derived_rsp
        except Exception:
            pass

    rsp_val = getattr(product, 'rsp', None)
    d = _to_decimal(rsp_val)
    if d is not None:
        return d

    val = getattr(product, 'display_rsp', None)
    d = _to_decimal(val)
    return d if d is not None else Decimal('0.00')


@register.filter
def display_bulk_total(product):
    """Compute bulk total using display_rsp fallback times pack_amount."""
    if not product:
        return Decimal('0.00')
    unit = display_rsp(product)
    try:
        pack = int(product.pack_amount()) if callable(product.pack_amount) else int(getattr(product, 'pack_amount', 1) or 1)
    except Exception:
        pack = 1
    try:
        return (unit * Decimal(pack)).quantize(Decimal('0.01'))
    except Exception:
        return Decimal('0.00')


@register.filter
def fix_currency(text):
    """Fix common mojibake for the pound symbol in rendered text.

    Replaces occurrences like 'Â£' or '��' with the proper '£'.
    Safe for plain strings; does not mark output as safe HTML.
    """
    try:
        s = str(text)
    except Exception:
        return text
    return s.replace('Â£', '£').replace('��', '£')
