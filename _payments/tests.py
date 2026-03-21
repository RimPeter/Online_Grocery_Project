from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from _catalog.models import All_Products
from _orders.models import Order, OrderItem
from _payments.models import Payment


@override_settings(
    STRIPE_PUBLIC_KEY='pk_test_123',
    STRIPE_SECRET_KEY='sk_test_123',
)
class CheckoutViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='checkout-user',
            password='test-pass-123',
            email='checkout@example.com',
            first_name='Checkout',
            last_name='User',
            phone='07123456789',
        )
        self.client.force_login(self.user)

        self.product = All_Products.objects.create(
            ga_product_id='ga-checkout-1',
            name='Test Product',
            price=Decimal('10.00'),
            list_position=1,
            url='https://example.com/products/test-product',
        )
        self.order = Order.objects.create(
            user=self.user,
            total=Decimal('10.00'),
            status='pending',
        )
        OrderItem.objects.create(
            order=self.order,
            product=self.product,
            quantity=1,
            price=Decimal('10.00'),
        )

    @patch('_payments.views.track_event')
    @patch('_payments.views.stripe.PaymentIntent.create')
    def test_checkout_view_uses_applied_basket_reward_discount_for_tracking(
        self,
        payment_intent_create_mock,
        track_event_mock,
    ):
        payment_intent_create_mock.return_value = {
            'id': 'pi_test_123',
            'client_secret': 'pi_test_secret_123',
        }

        response = self.client.get(reverse('checkout', args=[self.order.id]))

        self.assertEqual(response.status_code, 200)
        payment = Payment.objects.get(order=self.order, user=self.user)
        self.assertEqual(payment.amount, Decimal('11.50'))
        self.assertEqual(response.context['basket_reward_discount'], Decimal('0.00'))
        self.assertEqual(response.context['grand_total'], Decimal('11.50'))

        checkout_started_call = track_event_mock.call_args_list[0]
        self.assertEqual(
            checkout_started_call.kwargs['properties']['discount_amount'],
            '0.00',
        )
