from django.db import models

class InternetPlan(models.Model):
    name = models.CharField(max_length=100)
    duration_hours = models.IntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} - {self.duration_hours}hr(s) @ {self.price}/="