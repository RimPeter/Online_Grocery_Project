from django import template
from decimal import Decimal, InvalidOperation

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
    """Return display unit RSP for a product with sensible fallbacks.

    Priority:
    1) Explicit annotated `display_rsp` when provided and non-zero
    2) If not bulk AND rsp == 0, compute rsp = price * 1.3
    3) Else use model `rsp` when present
    Fallback to Decimal('0.00')
    """
    if not product:
        return Decimal('0.00')

    # 1) annotated display_rsp when present/non-zero
    val = getattr(product, 'display_rsp', None)
    if _to_decimal(val) not in (None, Decimal('0')):
        return _to_decimal(val)

    # 2) for non-bulk items with rsp == 0, derive from cost price
    try:
        is_bulk = bool(getattr(product, 'is_bulk'))
    except Exception:
        is_bulk = False
    rsp_val = getattr(product, 'rsp', None)
    rsp_dec = _to_decimal(rsp_val)
    if not is_bulk and rsp_dec == Decimal('0'):
        base_price = _to_decimal(getattr(product, 'price', None))
        if base_price is not None:
            try:
                return (base_price * Decimal('1.30')).quantize(Decimal('0.01'))
            except Exception:
                pass

    # 3) fallback to model rsp
    d = _to_decimal(rsp_val)
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
