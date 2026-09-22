"""Isolated tests: never use deployment databases, email, or Stripe credentials."""
import os

os.environ['GROCERY_TESTING'] = '1'
os.environ['DEBUG'] = 'False'
os.environ['SECRET_KEY'] = 'test-only-not-for-deployment'
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
from .settings import *  # noqa: F403,E402

DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}}
if os.environ.get('TEST_DATABASE_URL'):
    DATABASES = {'default': dj_database_url.parse(os.environ['TEST_DATABASE_URL'])}
EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']
STRIPE_SECRET_KEY = 'sk_test_mock'
STRIPE_PUBLIC_KEY = 'pk_test_mock'
STRIPE_WEBHOOK_SECRET = 'whsec_test'
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SECURE_SSL_REDIRECT = False
ALLOWED_HOSTS = ['testserver', 'localhost', '127.0.0.1']
