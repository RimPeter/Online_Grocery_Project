from decimal import Decimal

from django.db.models import Sum

from .models import ReferralCreditLedger, User


NEWCOMER_DISCOUNT_AMOUNT = Decimal('5.00')
REFERRER_REWARD_AMOUNT = Decimal('1.00')
SUCCESSFUL_ORDER_STATUSES = ('paid', 'processed', 'delivered')


class ReferralError(ValueError):
    pass


def normalize_referral_code(value):
    return (value or '').strip().upper()


def user_has_successful_orders(user, *, exclude_order_id=None):
    if not user or not getattr(user, 'pk', None):
        return False

    qs = user.order_set.filter(status__in=SUCCESSFUL_ORDER_STATUSES)
    if exclude_order_id is not None:
        qs = qs.exclude(pk=exclude_order_id)
    return qs.exists()


def can_attach_referral_code(user):
    if not user or not getattr(user, 'pk', None):
        return False
    if user.referred_by_id:
        return False
    return not user_has_successful_orders(user)


def resolve_referrer(code):
    normalized = normalize_referral_code(code)
    if not normalized:
        return None
    return User.objects.filter(referral_code__iexact=normalized).first()


def attach_referral_code(user, code):
    normalized = normalize_referral_code(code)
    if not normalized:
        raise ReferralError('Enter a valid referral code.')
    if not can_attach_referral_code(user):
        raise ReferralError('Referral code can only be attached before your first paid order.')

    referrer = resolve_referrer(normalized)
    if referrer is None:
        raise ReferralError('Referral code not found.')
    if referrer.pk == user.pk:
        raise ReferralError('You cannot use your own referral code.')

    user.referred_by = referrer
    user.save(update_fields=['referred_by'])
    return referrer


def has_used_newcomer_discount(user, *, exclude_order_id=None):
    if not user or not getattr(user, 'pk', None):
        return False

    qs = user.order_set.filter(
        status__in=SUCCESSFUL_ORDER_STATUSES,
        newcomer_referral_discount__gt=Decimal('0.00'),
    )
    if exclude_order_id is not None:
        qs = qs.exclude(pk=exclude_order_id)
    return qs.exists()


def should_apply_newcomer_discount(user, *, order=None):
    if not user or not getattr(user, 'pk', None):
        return False
    if not user.referred_by_id:
        return False

    exclude_order_id = getattr(order, 'pk', None)
    return not has_used_newcomer_discount(user, exclude_order_id=exclude_order_id)


def get_available_referral_credit(user):
    if not user or not getattr(user, 'pk', None):
        return Decimal('0.00')

    total = (
        ReferralCreditLedger.objects
        .filter(user=user)
        .aggregate(total=Sum('amount'))
        .get('total')
    ) or Decimal('0.00')
    return Decimal(total).quantize(Decimal('0.01'))


def build_referral_discounts(user, *, order=None, pre_credit_total=Decimal('0.00')):
    pre_credit_total = Decimal(str(pre_credit_total or 0)).quantize(Decimal('0.01'))
    if pre_credit_total <= Decimal('0.00'):
        return {
            'newcomer_referral_discount': Decimal('0.00'),
            'referral_credit_discount': Decimal('0.00'),
            'available_referral_credit': get_available_referral_credit(user),
        }

    newcomer_discount = Decimal('0.00')
    if should_apply_newcomer_discount(user, order=order):
        newcomer_discount = min(NEWCOMER_DISCOUNT_AMOUNT, pre_credit_total)

    remaining = pre_credit_total - newcomer_discount
    available_credit = get_available_referral_credit(user)
    referral_credit_discount = min(available_credit, remaining)

    return {
        'newcomer_referral_discount': newcomer_discount.quantize(Decimal('0.01')),
        'referral_credit_discount': referral_credit_discount.quantize(Decimal('0.01')),
        'available_referral_credit': available_credit,
    }


def finalize_referral_rewards(order):
    user = getattr(order, 'user', None)
    if not user or not getattr(order, 'pk', None):
        return

    if (
        getattr(order, 'referral_credit_discount', Decimal('0.00')) > Decimal('0.00')
        and not ReferralCreditLedger.objects.filter(
            user=user,
            order=order,
            entry_type='credit_spent',
        ).exists()
    ):
        ReferralCreditLedger.objects.create(
            user=user,
            order=order,
            entry_type='credit_spent',
            amount=-Decimal(order.referral_credit_discount).quantize(Decimal('0.01')),
        )

    if (
        user.referred_by_id
        and not ReferralCreditLedger.objects.filter(
            user=user.referred_by,
            order=order,
            entry_type='referrer_reward',
        ).exists()
    ):
        ReferralCreditLedger.objects.create(
            user=user.referred_by,
            order=order,
            entry_type='referrer_reward',
            amount=REFERRER_REWARD_AMOUNT,
        )
