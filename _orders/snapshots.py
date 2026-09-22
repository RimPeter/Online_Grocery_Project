from decimal import Decimal
from types import SimpleNamespace
from .pricing import calculate_checkout_totals


def order_pricing(order):
    snapshot = getattr(order, 'checkout_snapshot', {}) or {}
    if snapshot.get('pricing'):
        return {key: Decimal(value) if isinstance(value, str) else value for key, value in snapshot['pricing'].items()}
    if getattr(order, 'status', 'pending') != 'pending':
        # Never reconstruct historical charges using today's business settings.
        return {'grand_total': Decimal(snapshot.get('recorded_paid_total', '0')),
                'delivery_charge': Decimal('0'), 'basket_reward_discount': Decimal('0'),
                'newcomer_referral_discount': order.newcomer_referral_discount,
                'referral_credit_discount': order.referral_credit_discount,
                'historical_total_unavailable': 'recorded_paid_total' not in snapshot}
    return calculate_checkout_totals(order.total, has_items=order.total > 0,
        newcomer_referral_discount=order.newcomer_referral_discount,
        referral_credit_discount=order.referral_credit_discount)


def invoice_context(order):
    snapshot = order.checkout_snapshot
    if order.snapshot_needs_review or snapshot.get('version') != 1:
        raise ValueError('This historical invoice needs review. Please contact support for a verified copy.')
    return {
        'default_address': SimpleNamespace(**snapshot['address']),
        'company': SimpleNamespace(**snapshot['company']) if snapshot['company'] else None,
        'customer': SimpleNamespace(**snapshot['customer']),
        **order_pricing(order),
    }
