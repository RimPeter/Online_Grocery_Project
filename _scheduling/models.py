from django.db import models
from _employees.models import Employee

class Schedule(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='schedules')
    approved_by = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='approved_schedules')
    date = models.DateField()
    shift_type = models.CharField(max_length=50)
    start_time = models.TimeField()
    end_time = models.TimeField()
    is_approved = models.BooleanField(default=False)
    notes = models.TextField(null=True, blank=True)
