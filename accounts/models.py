from django.contrib.auth.models import AbstractUser
from django.db import models


class CustomUser(AbstractUser):

    ROLE_CHOICES = (
        ("ADMIN", "Admin"),
        ("CUSTOMER", "Customer"),
    )

    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default="CUSTOMER"
    )

    phone = models.CharField(
        max_length=15,
        blank=True,
        null=True
    )

    @property
    def display_name(self):
        if self.first_name:
            if self.last_name:
                return f"{self.first_name} {self.last_name}"
            return self.first_name
        name = self.username
        if "@" in name:
            name = name.split("@")[0]
        return name.replace(".", " ").replace("_", " ").title()

    def __str__(self):
        return self.username