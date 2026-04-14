from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from _accounts.models import ReferralCreditLedger
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


@override_settings(
    STRIPE_PUBLIC_KEY='pk_test_123',
    STRIPE_SECRET_KEY='sk_test_123',
)
class CheckoutFallbackPricingTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='checkout-fallback-user',
            password='test-pass-123',
            email='checkout-fallback@example.com',
            first_name='Checkout',
            last_name='Fallback',
            phone='07123456789',
        )
        self.client.force_login(self.user)
        self.product = All_Products.objects.create(
            ga_product_id='ga-checkout-fallback-1',
            name='Fallback Product',
            price=Decimal('15.48'),
            list_position=1,
            url='https://example.com/products/fallback-product',
        )

    @patch('_payments.views.track_event')
    @patch('_payments.views.stripe.PaymentIntent.create')
    def test_checkout_fallback_creates_order_using_customer_pricing(
        self,
        payment_intent_create_mock,
        track_event_mock,
    ):
        payment_intent_create_mock.return_value = {
            'id': 'pi_test_456',
            'client_secret': 'pi_test_secret_456',
        }

        session = self.client.session
        session['cart'] = {str(self.product.id): 2}
        session.save()

        response = self.client.get(reverse('checkout', args=[999999]))

        self.assertEqual(response.status_code, 200)

        order = Order.objects.get(user=self.user, status='pending')
        self.assertEqual(order.total, Decimal('40.24'))
        self.assertEqual(order.items.count(), 1)
        self.assertEqual(order.items.first().price, Decimal('20.12'))

        payment = Payment.objects.get(order=order, user=self.user)
        self.assertEqual(payment.amount, Decimal('41.74'))
        self.assertEqual(response.context['grand_total'], Decimal('41.74'))


@override_settings(
    STRIPE_PUBLIC_KEY='pk_test_123',
    STRIPE_SECRET_KEY='sk_test_123',
)
class ReferralCheckoutTests(TestCase):
    def setUp(self):
        self.User = get_user_model()
        self.referrer = self.User.objects.create_user(
            username='referrer-user',
            password='test-pass-123',
            email='referrer@example.com',
            first_name='Referrer',
            last_name='User',
            phone='07111111111',
        )
        self.user = self.User.objects.create_user(
            username='referred-user',
            password='test-pass-123',
            email='referred@example.com',
            first_name='Referred',
            last_name='User',
            phone='07222222222',
            referred_by=self.referrer,
        )
        self.client.force_login(self.user)
        self.product = All_Products.objects.create(
            ga_product_id='ga-checkout-referral-1',
            name='Referral Product',
            price=Decimal('10.00'),
            list_position=1,
            url='https://example.com/products/referral-product',
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
    def test_checkout_applies_newcomer_discount(self, payment_intent_create_mock, track_event_mock):
        payment_intent_create_mock.return_value = {
            'id': 'pi_test_newcomer',
            'client_secret': 'pi_test_secret_newcomer',
        }

        response = self.client.get(reverse('checkout', args=[self.order.id]))

        self.assertEqual(response.status_code, 200)
        self.order.refresh_from_db()
        self.assertEqual(self.order.newcomer_referral_discount, Decimal('5.00'))
        self.assertEqual(response.context['grand_total'], Decimal('6.50'))

    @patch('_payments.views.send_paid_order_notification')
    @patch('_payments.views.track_event')
    def test_payment_success_awards_referrer_and_spends_credit_once(self, track_event_mock, notification_mock):
        self.order.newcomer_referral_discount = Decimal('5.00')
        self.order.referral_credit_discount = Decimal('0.00')
        self.order.save(update_fields=['newcomer_referral_discount', 'referral_credit_discount'])
        payment = Payment.objects.create(
            user=self.user,
            order=self.order,
            amount=Decimal('6.50'),
            currency='gbp',
            status='created',
        )

        response = self.client.get(reverse('payment_success') + f'?payment_id={payment.id}')

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            ReferralCreditLedger.objects.filter(
                user=self.referrer,
                order=self.order,
                entry_type='referrer_reward',
                amount=Decimal('1.00'),
            ).exists()
        )

        second_response = self.client.get(reverse('payment_success') + f'?payment_id={payment.id}')
        self.assertEqual(second_response.status_code, 200)
        self.assertEqual(
            ReferralCreditLedger.objects.filter(
                user=self.referrer,
                order=self.order,
                entry_type='referrer_reward',
            ).count(),
            1,
        )

    @patch('_payments.views.track_event')
    @patch('_payments.views.stripe.PaymentIntent.create')
    def test_checkout_auto_applies_referral_credit_balance(self, payment_intent_create_mock, track_event_mock):
        ReferralCreditLedger.objects.create(
            user=self.user,
            order=None,
            entry_type='referrer_reward',
            amount=Decimal('3.00'),
        )
        payment_intent_create_mock.return_value = {
            'id': 'pi_test_wallet',
            'client_secret': 'pi_test_secret_wallet',
        }

        response = self.client.get(reverse('checkout', args=[self.order.id]))

        self.assertEqual(response.status_code, 200)
        self.order.refresh_from_db()
        self.assertEqual(self.order.referral_credit_discount, Decimal('3.00'))
        self.assertEqual(response.context['grand_total'], Decimal('3.50'))
