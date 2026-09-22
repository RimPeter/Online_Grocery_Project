from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse


class AccountSecurityTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='secure', password='password123', email='secure@example.com')

    def test_login_rejects_external_next(self):
        response = self.client.post(reverse('login') + '?next=https://evil.example/', {'username': 'secure', 'password': 'password123'})
        self.assertEqual(response.url, reverse('home'))

    def test_login_accepts_local_next(self):
        response = self.client.post(reverse('login'), {'username': 'secure', 'password': 'password123', 'next': '/accounts/profile/'})
        self.assertEqual(response.url, '/accounts/profile/')

    def test_login_limit_survives_fresh_sessions(self):
        for _ in range(5):
            Client().post(reverse('login'), {'username': 'secure', 'password': 'wrong'})
        fresh = Client()
        response = fresh.post(reverse('login'), {'username': 'secure', 'password': 'password123'})
        self.assertContains(response, 'Too many attempts')
        self.assertNotIn('_auth_user_id', fresh.session)

    def test_logout_requires_post(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse('logout')).status_code, 405)
        self.assertEqual(self.client.post(reverse('logout')).status_code, 302)

    def test_management_report_is_not_public(self):
        self.assertEqual(self.client.get(reverse('_product_management:missing_retail_ean')).status_code, 302)
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse('_product_management:missing_retail_ean')).status_code, 302)

    def test_cart_mutations_require_post(self):
        self.assertEqual(self.client.get(reverse('add_to_cart', args=[1])).status_code, 405)
        self.assertEqual(self.client.get(reverse('update_cart')).status_code, 405)
