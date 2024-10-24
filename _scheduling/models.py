from django.db import models
from _employees.models import Employee
from django.core.exceptions import ValidationError

class Schedule(models.Model):
    SHIFT_TYPE_CHOICES = [
        ('morning', 'Morning'),
        ('afternoon', 'Afternoon'),
        ('evening', 'Evening'),
        ('night', 'Night'),
    ]

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='schedules')
    approved_by = models.ForeignKey(
        Employee, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_schedules'
    )
    date = models.DateField()
    shift_type = models.CharField(
        max_length=20, choices=SHIFT_TYPE_CHOICES
    )
    start_time = models.TimeField()
    end_time = models.TimeField()
    is_approved = models.BooleanField(default=False)
    notes = models.TextField(null=True, blank=True)

    def clean(self):
        if self.approved_by and self.employee == self.approved_by:
            raise ValidationError("An employee cannot approve their own schedule.")

    def __str__(self):
        return f"Schedule for {self.employee.user.get_full_name()} on {self.date}"