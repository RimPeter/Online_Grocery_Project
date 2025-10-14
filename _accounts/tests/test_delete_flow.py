from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model


class DeleteAccountFlowTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username='deleteme',
            email='deleteme@example.com',
            phone='1234567890',
            password='pass12345',
        )

    def test_delete_redirects_to_confirmation_and_logs_out(self):
        # Log the user in
        self.client.login(username='deleteme', password='pass12345')

        # Post correct password to delete endpoint
        resp = self.client.post(reverse('delete_account'), data={'password': 'pass12345', 'confirm': 'DELETE'})

        # Should redirect to confirmation page
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, reverse('account_deleted'))

        # Follow to confirmation page
        resp2 = self.client.get(resp.url)
        self.assertEqual(resp2.status_code, 200)
        self.assertContains(resp2, 'Account Deleted')

        # User should be deleted
        User = get_user_model()
        self.assertFalse(User.objects.filter(username='deleteme').exists())

        # Session should be logged out now; profile should redirect to login
        resp3 = self.client.get(reverse('profile'))
        self.assertEqual(resp3.status_code, 302)
        self.assertIn('/accounts/login/', resp3.url)
