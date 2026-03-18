import logging
from decimal import Decimal
from types import SimpleNamespace

from django.conf import settings
from django.core.mail import send_mail

from .pricing import calculate_checkout_totals


logger = logging.getLogger(__name__)

PAID_ORDER_NOTIFICATION_EMAIL = 'primaszecsi@gmail.com'


def send_paid_order_notification(order):
    if not order or not getattr(order, 'pk', None):
        return False

    try:
        if getattr(order, 'status', None) != 'paid':
            return False

        items_manager = getattr(order, 'items', None)
        if hasattr(items_manager, 'select_related'):
            items = list(items_manager.select_related('product').all())
        elif hasattr(items_manager, 'all'):
            items = list(items_manager.all())
        else:
            items = list(items_manager or [])

        subtotal = sum((item.price * item.quantity) for item in items)
        if not items:
            subtotal = Decimal(str(getattr(order, 'total', 0) or 0))
        pricing = calculate_checkout_totals(subtotal, has_items=bool(items or subtotal > 0))

        user = getattr(order, 'user', None) or SimpleNamespace(
            get_full_name=lambda: '',
            username='',
            email='',
            phone='',
        )
        customer_name = user.get_full_name() or user.username or user.email
        delivery_bits = []
        if getattr(order, 'delivery_date', None):
            delivery_bits.append(order.delivery_date.strftime('%Y-%m-%d'))
        if getattr(order, 'delivery_time', None):
            delivery_bits.append(order.delivery_time.strftime('%H:%M'))

        lines = [
            f"New paid order: #{order.id}",
            "",
            f"Customer: {customer_name}",
            f"Email: {getattr(user, 'email', '') or '-'}",
            f"Phone: {getattr(user, 'phone', '') or '-'}",
            f"Subtotal: £{subtotal:.2f}",
            f"Delivery: £{pricing['delivery_charge']:.2f}",
            f"Basket reward: -£{pricing['basket_reward_discount']:.2f}",
            f"Grand total: £{pricing['grand_total']:.2f}",
            f"Delivery slot: {' '.join(delivery_bits) if delivery_bits else '-'}",
            "",
            "Items:",
        ]

        if items:
            for item in items:
                product_name = getattr(getattr(item, 'product', None), 'name', 'Unknown product')
                lines.append(f"- {product_name} x {item.quantity} @ £{item.price:.2f}")
        else:
            lines.append("- No order items found.")

        from_email = (
            getattr(settings, 'DEFAULT_FROM_EMAIL', None)
            or getattr(settings, 'EMAIL_HOST_USER', None)
            or 'no-reply@example.com'
        )

        send_mail(
            f"New paid order #{order.id}",
            '\n'.join(lines),
            from_email,
            [PAID_ORDER_NOTIFICATION_EMAIL],
            fail_silently=False,
        )
        return True
    except Exception:
        logger.exception("Failed to send paid order notification for order_id=%s", getattr(order, 'pk', None))
        return False
