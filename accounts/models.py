from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = "admin", "Admin"
        MANAGER = "manager", "Manager"
        AGENT = "agent", "Agent"

    role = models.CharField(max_length=20, choices=Role.choices, default=Role.AGENT)
    phone = models.CharField(max_length=30, blank=True)

    @property
    def sees_all_leads(self):
        """Admins and managers see every lead; agents see their own and unassigned ones."""
        return self.is_superuser or self.role in (self.Role.ADMIN, self.Role.MANAGER)

    @property
    def is_admin(self):
        """Only admins approve listings for the public website."""
        return self.is_superuser or self.role == self.Role.ADMIN

    @property
    def can_manage(self):
        return self.sees_all_leads

    def __str__(self):
        return self.get_full_name() or self.username
