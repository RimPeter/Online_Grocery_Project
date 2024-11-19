from django.db import models

class Supplier(models.Model):
    company_name = models.CharField(max_length=255)
    company_id = models.CharField(max_length=100, unique=True)
    contact_person = models.CharField(max_length=100,null=True, blank=True)
    email = models.EmailField()
    phone = models.CharField(max_length=15)
    house_number = models.CharField(max_length=10)
    street_name1 = models.CharField(max_length=100)
    street_name2 = models.CharField(max_length=100, null=True, blank=True)
    city = models.CharField(max_length=50)
    postal_code = models.CharField(max_length=20)
    website = models.URLField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    bank_name = models.CharField(max_length=100)
    bank_account = models.CharField(max_length=100)
    sort_code = models.CharField(max_length=6)
    VAT_number = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.company_name
    


