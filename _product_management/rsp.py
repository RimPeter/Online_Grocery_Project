from decimal import Decimal, InvalidOperation

from django.db.models import DecimalField, ExpressionWrapper, F, Value


DEFAULT_RSP_MULTIPLIER = Decimal('1.30')


def _to_decimal(value, *, default=Decimal('0.00')):
    try:
        return Decimal(str(value)).quantize(Decimal('0.01'))
    except (InvalidOperation, TypeError, ValueError):
        return default


def get_rsp_multiplier():
    try:
        from .models import BasketPricingSettings

        multiplier = _to_decimal(
            BasketPricingSettings.get_solo().rsp_multiplier,
            default=DEFAULT_RSP_MULTIPLIER,
        )
        return multiplier if multiplier > Decimal('0.00') else DEFAULT_RSP_MULTIPLIER
    except Exception:
        return DEFAULT_RSP_MULTIPLIER


def calculate_rsp_from_cost(cost_price, *, multiplier=None):
    cost = _to_decimal(cost_price, default=None)
    if cost is None:
        return None

    active_multiplier = multiplier if multiplier is not None else get_rsp_multiplier()
    active_multiplier = _to_decimal(active_multiplier, default=DEFAULT_RSP_MULTIPLIER)
    if active_multiplier <= Decimal('0.00'):
        active_multiplier = DEFAULT_RSP_MULTIPLIER

    return (cost * active_multiplier).quantize(Decimal('0.01'))


def build_rsp_expression(price_field='price', *, multiplier=None):
    active_multiplier = multiplier if multiplier is not None else get_rsp_multiplier()
    active_multiplier = _to_decimal(active_multiplier, default=DEFAULT_RSP_MULTIPLIER)
    if active_multiplier <= Decimal('0.00'):
        active_multiplier = DEFAULT_RSP_MULTIPLIER

    return ExpressionWrapper(
        F(price_field) * Value(active_multiplier),
        output_field=DecimalField(max_digits=10, decimal_places=2),
    )
