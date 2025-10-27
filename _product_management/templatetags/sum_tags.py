from django import template

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
