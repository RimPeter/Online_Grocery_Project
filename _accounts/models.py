from django.db import models
from django.contrib.auth.models import AbstractUser, Group, Permission
import uuid
from django.conf import settings
from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower # For case-insensitive constraints
from django.utils import timezone


class Company(models.Model):
    # Core identity
    name = models.CharField(max_length=150)
    legal_name = models.CharField(max_length=255, blank=True)
    slug = models.SlugField(max_length=150, unique=True)

    # Contact
    email = models.EmailField()
    support_email = models.EmailField(blank=True)
    phone = models.CharField(max_length=32, blank=True)
    website = models.URLField(blank=True)

    # Registration / tax
    company_number = models.CharField(max_length=64, blank=True)   # e.g. Companies House No.
    vat_number = models.CharField(max_length=64, blank=True)       # e.g. GB123456789
    tax_id = models.CharField(max_length=64, blank=True)           # other jurisdictions

    # Address (kept separate from user Address)
    address_line1 = models.CharField(max_length=255)
    address_line2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100)
    region = models.CharField(max_length=100, blank=True)          # county/state/province
    postal_code = models.CharField(max_length=20)
    country = models.CharField(max_length=100, default="United Kingdom")

    # Branding
    logo = models.ImageField(upload_to="company_logos/", null=True, blank=True)

    # Invoicing / locale
    currency_code = models.CharField(max_length=3, default="GBP")  # ISO 4217, e.g. GBP/EUR/USD
    timezone = models.CharField(max_length=64, default="Europe/London")
    invoice_prefix = models.CharField(max_length=20, default="INV")  # e.g. "INV"
    invoice_footer = models.TextField(blank=True)  # shown at invoice bottom

    # Misc
    notes = models.TextField(blank=True)
    is_default = models.BooleanField(default=False)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            # Case-insensitive unique name
            models.UniqueConstraint(Lower('name'), name='uniq_company_name_lower'),
            # Ensure only one default company exists (PostgreSQL partial index)
            models.UniqueConstraint(
                fields=['is_default'],
                condition=Q(is_default=True),
                name='unique_default_company',
            ),
        ]
        ordering = ['name']

    def __str__(self):
        return self.name

    @classmethod
    def get_default(cls):
        """Return the default company (or the first one as a safe fallback)."""
        return cls.objects.filter(is_default=True).first() or cls.objects.order_by('id').first()

    @property
    def address_one_line(self):
        parts = [self.address_line1, self.address_line2, self.city, self.region, self.postal_code, self.country]
        return ", ".join([p for p in parts if p])

class User(AbstractUser):
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=15)
    is_active = models.BooleanField(default=True)

    groups = models.ManyToManyField(
        Group,
        related_name='custom_user_set',  # Add a unique related_name
        blank=True,
        help_text='The groups this user belongs to.',
        verbose_name='groups',
    )
    user_permissions = models.ManyToManyField(
        Permission,
        related_name='custom_user_set',  # Add a unique related_name
        blank=True,
        help_text='Specific permissions for this user.',
        verbose_name='user permissions',
    )
    
    class Meta:
        constraints = [
            # Case-insensitive unique username
            models.UniqueConstraint(
                Lower('username'),
                name='uniq_user_username_lower'
            ),
            # Case-insensitive unique email (skip NULLs)
            models.UniqueConstraint(
                Lower('email'),
                condition=Q(email__isnull=False),
                name='uniq_user_email_lower'
            ),
        ]

    def __str__(self):
        return self.email

class Address(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='addresses')
    street_address = models.CharField(max_length=255)
    house_number = models.CharField(max_length=20)
    apartment = models.CharField(max_length=50, null=True, blank=True)
    city = models.CharField(max_length=50)
    postal_code = models.CharField(max_length=20)
    delivery_instructions = models.TextField(null=True, blank=True)
    is_default = models.BooleanField(default=False)
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['user'],
                condition=Q(is_default=True),
                name='unique_default_address_per_user',
            ),
        ]
    def __str__(self):
        street = f"{self.street_address} {self.house_number}".strip()
        return f"{street}, {self.city}"
    

class VerificationCode(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='verification_code'
    )
    code = models.CharField(max_length=50, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_used = models.BooleanField(default=False)

    def __str__(self):
        return f"Verification code for {self.user.email}"
    
class PendingSignup(models.Model):
    username = models.CharField(max_length=150)
    email = models.EmailField()
    phone = models.CharField(max_length=32, blank=True)
    password_hash = models.CharField(max_length=128)
    code = models.CharField(max_length=32)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    attempts = models.PositiveIntegerField(default=0)
    requester_ip = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(Lower('username'), name='uniq_pending_username_lower'),
            models.UniqueConstraint(Lower('email'), condition=Q(email__isnull=False), name='uniq_pending_email_lower'),
        ]

    def is_expired(self):
        return timezone.now() > self.expires_at
    
    
class ContactMessage(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='contact_messages')
    subject = models.CharField(max_length=200, blank=True)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    archived = models.BooleanField(default=False, db_index=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        subj = self.subject or 'No subject'
        return f'Contact from {self.user} - {subj}'


class ContactMessageActive(ContactMessage):
    class Meta:
        proxy = True
        verbose_name = 'Contact message (active)'
        verbose_name_plural = 'Contact messages (active)'


class ContactMessageArchived(ContactMessage):
    class Meta:
        proxy = True
        verbose_name = 'Contact message (archive)'
        verbose_name_plural = 'Contact messages (archive)'
