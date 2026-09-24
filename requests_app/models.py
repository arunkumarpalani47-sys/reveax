from django.db import models

STATUS_CHOICES = [
    ("PENDING",  "Pending"),
    ("APPROVED", "Approved"),
    ("REJECTED", "Rejected"),
]

class PartnerRequest(models.Model):
    full_name      = models.CharField(max_length=150)
    email          = models.EmailField()
    phone          = models.CharField(max_length=20)
    business_name  = models.CharField(max_length=200, blank=True)
    num_vehicles   = models.PositiveIntegerField(default=1)
    city           = models.CharField(max_length=100)
    message        = models.TextField(blank=True)
    status         = models.CharField(max_length=10, choices=STATUS_CHOICES, default="PENDING")
    reject_reason  = models.TextField(blank=True)
    applied_at     = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-applied_at"]

    def __str__(self):
        return f"{self.full_name} — {self.status}"


class DriverRequest(models.Model):
    full_name      = models.CharField(max_length=150)
    email          = models.EmailField()
    phone          = models.CharField(max_length=20)
    license_number = models.CharField(max_length=50)
    vehicle_pref   = models.CharField(max_length=100, blank=True)
    city           = models.CharField(max_length=100)
    experience_yrs = models.PositiveIntegerField(default=0)
    status         = models.CharField(max_length=10, choices=STATUS_CHOICES, default="PENDING")
    reject_reason  = models.TextField(blank=True)
    applied_at     = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-applied_at"]

    def __str__(self):
        return f"{self.full_name} — {self.status}"
