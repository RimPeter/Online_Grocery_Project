from django import template
from datetime import time
from decimal import Decimal, InvalidOperation

register = template.Library()

@register.filter
def sum_attr(items, attr):
    """Sum a given attribute across a list or queryset of dicts or objects."""
    total = 0
    for i in items:
        value = None
        # Handle both object and dict types
        if isinstance(i, dict):
            value = i.get(attr)
        else:
            value = getattr(i, attr, None)

        try:
            total += float(value or 0)
        except (TypeError, ValueError):
            continue
    return total

@register.filter
def sum_coalesce(items, attrs):
    """Sum the first non-empty attribute among a comma-separated list per item.

    Example: {{ items|sum_coalesce:"display_rsp,product__rsp" }}
    """
    if not items:
        return 0
    try:
        names = [a.strip() for a in str(attrs).split(',') if a and a.strip()]
    except Exception:
        names = [str(attrs)]
    total = 0
    for i in items:
        value = None
        for name in names:
            if isinstance(i, dict):
                v = i.get(name)
            else:
                v = getattr(i, name, None)
            if v not in (None, ''):
                value = v
                break
        try:
            total += float(value or 0)
        except (TypeError, ValueError):
            continue
    return total


@register.filter
def timeslot_label(value):
    """Map a delivery time (Time or 'HH:MM' string) to a human label.

    Example: 09:00 -> '9am - 12pm'. If no match, returns the 'HH:MM' string
    or empty string when value is falsy.
    """
    if not value:
        return ""
    try:
        if isinstance(value, time):
            key = value.strftime('%H:%M')
        else:
            s = str(value).strip()
            key = s[:5]
    except Exception:
        return ""

    mapping = {
        '09:00': '9am - 12pm',
        '10:00': '10am - 1pm',
        '11:00': '11am - 2pm',
        '12:00': '12pm - 3pm',
        '13:00': '1pm - 4pm',
        '14:00': '2pm - 5pm',
        '15:00': '3pm - 6pm',
        '16:00': '4pm - 7pm',
        '17:00': '5pm - 8pm',
        '18:00': '6pm - 9pm',
        '19:00': '7pm - 10pm',
    }
    return mapping.get(key, key)


@register.filter
def add_delivery_if_paid(total, status):
    """Add £1.50 delivery to total if order status is paid/processed/delivered.

    Usage: {{ total|add_delivery_if_paid:order.status }}
    Accepts numeric or Decimal totals; returns a Decimal.
    """
    try:
        amt = Decimal(str(total or 0))
    except (InvalidOperation, ValueError, TypeError):
        amt = Decimal('0.00')

    try:
        st = (status or '').strip().lower()
    except Exception:
        st = ''

    if st in ('paid', 'processed', 'delivered'):
        amt += Decimal('1.50')
    return amt
