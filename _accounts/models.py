from django.db import models

class User(AbstractUser):
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=15)
    is_active = models.BooleanField(default=True)

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

    def __str__(self):
        return f"{self.street_address}, {self.city}"