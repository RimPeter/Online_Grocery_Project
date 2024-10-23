from django.db import models

class Department(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField()

class Employee(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='employee_profile')
    department = models.ForeignKey(Department, on_delete=models.CASCADE)
    employee_type = models.CharField(max_length=50)
    employment_status = models.CharField(max_length=50)
    date_of_birth = models.DateField()
    emergency_contact_name = models.CharField(max_length=100)
    emergency_contact_phone = models.CharField(max_length=15)
    hire_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    hourly_rate = models.DecimalField(max_digits=10, decimal_places=2)
    id_document = models.CharField(max_length=255)
    contract_document = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

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

class StoreStaffProfile(models.Model):
    employee = models.OneToOneField(Employee, on_delete=models.CASCADE, related_name='store_staff_profile')
    specialization = models.CharField(max_length=100)
    is_shift_supervisor = models.BooleanField(default=False)
    food_safety_cert = models.BooleanField(default=False)
    food_safety_expiry = models.DateField(null=True, blank=True)

class ManagerProfile(models.Model):
    employee = models.OneToOneField(Employee, on_delete=models.CASCADE, related_name='manager_profile')
    level = models.CharField(max_length=50)
    budget_limit = models.DecimalField(max_digits=10, decimal_places=2)
