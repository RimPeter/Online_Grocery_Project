from django.db import models
from django.contrib.auth.models import AbstractUser, Group, Permission
import uuid
from django.conf import settings
from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower # For case-insensitive constraints
from django.utils import timezone

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
        return f"{self.street_address}, {self.city}"
    

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
    
    