from django.db import models

class User(models.Model):
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    phone = models.CharField(max_length=15)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

class Address(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='addresses')
    street_address = models.CharField(max_length=255)
    apartment = models.CharField(max_length=50, null=True, blank=True)
    city = models.CharField(max_length=50)
    postal_code = models.CharField(max_length=20)
    delivery_instructions = models.TextField(null=True, blank=True)
    is_default = models.BooleanField(default=False)
