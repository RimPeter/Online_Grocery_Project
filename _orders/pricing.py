from decimal import Decimal, InvalidOperation


DEFAULT_MINIMUM_ORDER_TOTAL = Decimal('40.00')
DEFAULT_DELIVERY_CHARGE = Decimal('1.50')
DEFAULT_BASKET_REWARD_THRESHOLD = Decimal('95.00')
DEFAULT_BASKET_REWARD_AMOUNT = Decimal('15.00')


def _to_money(value):
    try:
        return Decimal(str(value or 0)).quantize(Decimal('0.01'))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal('0.00')


def get_basket_pricing_settings():
    try:
        from _product_management.models import BasketPricingSettings

        obj = BasketPricingSettings.get_solo()
        return {
            'minimum_order_total': _to_money(obj.minimum_order_total),
            'delivery_charge': _to_money(obj.delivery_charge),
            'discount_threshold': _to_money(obj.discount_threshold),
            'discount_amount': _to_money(obj.discount_amount),
        }
    except Exception:
        return {
            'minimum_order_total': DEFAULT_MINIMUM_ORDER_TOTAL,
            'delivery_charge': DEFAULT_DELIVERY_CHARGE,
            'discount_threshold': DEFAULT_BASKET_REWARD_THRESHOLD,
            'discount_amount': DEFAULT_BASKET_REWARD_AMOUNT,
        }


def resolve_customer_unit_price(product):
    from _product_management.rsp import calculate_rsp_from_cost

    derived_rsp = calculate_rsp_from_cost(getattr(product, 'price', None))
    if derived_rsp is not None:
        return derived_rsp

    fallback_rsp = _to_money(getattr(product, 'rsp', None))
    if fallback_rsp > Decimal('0.00'):
        return fallback_rsp

    return _to_money(getattr(product, 'price', None))


def calculate_session_cart_subtotal(cart):
    if not isinstance(cart, dict) or not cart:
        return Decimal('0.00')

    from _catalog.models import All_Products

    product_ids = [int(pid) for pid in cart.keys() if str(pid).isdigit()]
    if not product_ids:
        return Decimal('0.00')

    products_by_id = {
        str(product.pk): product
        for product in All_Products.objects.filter(pk__in=product_ids)
    }

    subtotal = Decimal('0.00')
    for pid, qty in cart.items():
        product = products_by_id.get(str(pid))
        if not product:
            continue
        try:
            quantity = int(qty)
        except (TypeError, ValueError):
            continue
        if quantity <= 0:
            continue
        subtotal += resolve_customer_unit_price(product) * quantity

    return subtotal.quantize(Decimal('0.01'))


def calculate_checkout_totals(
    subtotal,
    *,
    has_items=True,
    pricing_settings=None,
    newcomer_referral_discount=Decimal('0.00'),
    referral_credit_discount=Decimal('0.00'),
):
    subtotal = _to_money(subtotal)
    has_items = bool(has_items)
    pricing_settings = pricing_settings or get_basket_pricing_settings()

    minimum_order_total = _to_money(pricing_settings.get('minimum_order_total'))
    delivery_charge = _to_money(pricing_settings.get('delivery_charge')) if has_items else Decimal('0.00')
    discount_threshold = _to_money(pricing_settings.get('discount_threshold'))
    discount_amount = _to_money(pricing_settings.get('discount_amount'))

    qualifies_for_basket_reward = has_items and subtotal >= discount_threshold
    basket_reward_discount = discount_amount if qualifies_for_basket_reward else Decimal('0.00')
    basket_reward_shortfall = max(Decimal('0.00'), discount_threshold - subtotal)
    minimum_order_shortfall = max(Decimal('0.00'), minimum_order_total - subtotal)
    pre_referral_total = (subtotal - basket_reward_discount + delivery_charge).quantize(Decimal('0.01'))

    newcomer_referral_discount = min(_to_money(newcomer_referral_discount), pre_referral_total)
    after_newcomer_total = pre_referral_total - newcomer_referral_discount
    referral_credit_discount = min(_to_money(referral_credit_discount), after_newcomer_total)
    grand_total = (after_newcomer_total - referral_credit_discount).quantize(Decimal('0.01'))
    if grand_total < Decimal('0.00'):
        grand_total = Decimal('0.00')

    return {
        'minimum_order_total': minimum_order_total,
        'minimum_order_shortfall': minimum_order_shortfall.quantize(Decimal('0.01')),
        'delivery_charge': delivery_charge,
        'pre_referral_total': pre_referral_total,
        'grand_total': grand_total,
        'basket_reward_discount': basket_reward_discount,
        'newcomer_referral_discount': newcomer_referral_discount,
        'referral_credit_discount': referral_credit_discount,
        'basket_reward_shortfall': basket_reward_shortfall.quantize(Decimal('0.01')),
        'basket_reward_threshold': discount_threshold,
        'basket_reward_amount': discount_amount,
        'qualifies_for_basket_reward': qualifies_for_basket_reward,
    }
