from django.contrib.auth import get_user_model
from django.test import TestCase

from _accounts.referrals import ReferralError, attach_referral_code, can_attach_referral_code
from _orders.models import Order


class ReferralRuleTests(TestCase):
    def setUp(self):
        self.User = get_user_model()
        self.referrer = self.User.objects.create_user(
            username='referrer',
            email='referrer@example.com',
            password='pass12345',
            phone='07111111111',
        )
        self.newcomer = self.User.objects.create_user(
            username='newcomer',
            email='newcomer@example.com',
            password='pass12345',
            phone='07222222222',
        )

    def test_can_attach_referral_code_before_first_paid_order(self):
        self.assertTrue(can_attach_referral_code(self.newcomer))

    def test_cannot_attach_referral_code_after_paid_order(self):
        Order.objects.create(user=self.newcomer, total='10.00', status='paid')

        self.assertFalse(can_attach_referral_code(self.newcomer))

    def test_attach_referral_code_sets_referrer_once(self):
        attach_referral_code(self.newcomer, self.referrer.referral_code)
        self.newcomer.refresh_from_db()

        self.assertEqual(self.newcomer.referred_by, self.referrer)
        with self.assertRaises(ReferralError):
            attach_referral_code(self.newcomer, self.referrer.referral_code)

    def test_cannot_self_refer(self):
        with self.assertRaises(ReferralError):
            attach_referral_code(self.referrer, self.referrer.referral_code)
