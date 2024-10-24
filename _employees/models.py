from django.db import models
from django.contrib.auth.models import User

class Department(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField()
    
    def __str__(self):
        return self.name

class Employee(models.Model):
    EMPLOYEE_TYPE_CHOICES = [
        ('full_time', 'Full-Time'),
        ('part_time', 'Part-Time'),
        ('contractor', 'Contractor'),
    ]

    EMPLOYMENT_STATUS_CHOICES = [
        ('active', 'Active'),
        ('on_leave', 'On Leave'),
        ('terminated', 'Terminated'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='employee_profile')
    department = models.ForeignKey(Department, on_delete=models.CASCADE)
    employee_type = models.CharField(
        max_length=20, choices=EMPLOYEE_TYPE_CHOICES
    )
    employment_status = models.CharField(
        max_length=20, choices=EMPLOYMENT_STATUS_CHOICES, default='active'
    )
    date_of_birth = models.DateField()
    emergency_contact_name = models.CharField(max_length=100)
    emergency_contact_phone = models.CharField(max_length=15)
    hire_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    hourly_rate = models.DecimalField(max_digits=10, decimal_places=2)
    id_document = models.FileField(upload_to='id_documents/')
    contract_document = models.FileField(upload_to='contracts/')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    # Added __str__ method
    def __str__(self):
        return self.user.get_full_name()

class DriverProfile(models.Model):
    employee = models.OneToOneField(Employee, on_delete=models.CASCADE, related_name='driver_profile')
    license_number = models.CharField(max_length=100, unique=True)
    license_type = models.CharField(max_length=50)
    license_expiry = models.DateField()
    vehicle_number = models.CharField(max_length=100)
    insurance_number = models.CharField(max_length=100)
    insurance_expiry = models.DateField()
    total_deliveries = models.IntegerField()
    average_rating = models.DecimalField(max_digits=5, decimal_places=2)
    
    def __str__(self):
        return f"Driver {self.employee.user.get_full_name()}"

class StoreStaffProfile(models.Model):
    employee = models.OneToOneField(Employee, on_delete=models.CASCADE, related_name='store_staff_profile')
    specialization = models.CharField(max_length=100)
    is_shift_supervisor = models.BooleanField(default=False)
    food_safety_cert = models.BooleanField(default=False)
    food_safety_expiry = models.DateField(null=True, blank=True)
    
    def __str__(self):
        return f"Store Staff {self.employee.user.get_full_name()}"

class ManagerProfile(models.Model):
    LEVEL_CHOICES = [
        ('junior', 'Junior Manager'),
        ('mid', 'Mid-level Manager'),
        ('senior', 'Senior Manager'),
        ('executive', 'Executive Manager'),
    ]

    employee = models.OneToOneField(Employee, on_delete=models.CASCADE, related_name='manager_profile')
    level = models.CharField(
        max_length=20, choices=LEVEL_CHOICES
    )
    budget_limit = models.DecimalField(max_digits=15, decimal_places=2)

    def __str__(self):
        return f"Manager {self.employee.user.get_full_name()}"
