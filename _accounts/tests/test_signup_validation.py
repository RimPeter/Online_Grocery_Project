from django.test import TestCase
from django.urls import reverse

from _accounts.models import PendingSignup


class SignupValidationTests(TestCase):
    def test_signup_rejects_missing_required_fields_server_side(self):
        response = self.client.post(reverse("signup"), data={})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Username is required")
        self.assertContains(response, "Email is required")
        self.assertContains(response, "Phone number is required")
        self.assertContains(response, "Password is required")
        self.assertFalse(PendingSignup.objects.exists())

    def test_signup_rejects_invalid_email_server_side(self):
        response = self.client.post(
            reverse("signup"),
            data={
                "username": "newshopper",
                "email": "not-an-email",
                "phone": "07123456789",
                "password1": "A-really-strong-passphrase-2048!",
                "password2": "A-really-strong-passphrase-2048!",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Enter a valid email address")
        self.assertFalse(PendingSignup.objects.exists())

    def test_signup_rejects_weak_password_server_side(self):
        response = self.client.post(
            reverse("signup"),
            data={
                "username": "newshopper",
                "email": "newshopper@example.com",
                "phone": "07123456789",
                "password1": "password",
                "password2": "password",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This password is too common.")
        self.assertFalse(PendingSignup.objects.exists())

    def test_signup_associates_password_mismatch_with_confirmation(self):
        response = self.client.post(
            reverse("signup"),
            data={
                "username": "newshopper",
                "email": "newshopper@example.com",
                "phone": "07123456789",
                "password1": "A-really-strong-passphrase-2048!",
                "password2": "A-different-strong-passphrase-2048!",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Passwords do not match")
        self.assertContains(response, 'aria-errormessage="password2-error"')
        self.assertFalse(PendingSignup.objects.exists())

    def test_signup_rejects_email_too_long_for_user_model(self):
        response = self.client.post(
            reverse("signup"),
            data={
                "username": "newshopper",
                "email": f"{'a' * 245}@example.com",
                "phone": "07123456789",
                "password1": "A-really-strong-passphrase-2048!",
                "password2": "A-really-strong-passphrase-2048!",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Email address is too long")
        self.assertFalse(PendingSignup.objects.exists())

    def test_signup_rejects_phone_too_long_for_user_model(self):
        response = self.client.post(
            reverse("signup"),
            data={
                "username": "newshopper",
                "email": "newshopper@example.com",
                "phone": "0712345678901234",
                "password1": "A-really-strong-passphrase-2048!",
                "password2": "A-really-strong-passphrase-2048!",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Phone number is too long")
        self.assertFalse(PendingSignup.objects.exists())
