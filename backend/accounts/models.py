from __future__ import annotations

from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Dashboard user. Role gates what the API and UI allow."""

    class Role(models.TextChoices):
        ADMIN = 'admin', 'Administrator'
        OPERATOR = 'operator', 'Operator'

    role = models.CharField(max_length=16, choices=Role.choices, default=Role.OPERATOR)

    @property
    def is_admin(self) -> bool:
        return self.role == self.Role.ADMIN or self.is_superuser

    def save(self, *args, **kwargs):
        # Superusers are always treated as admins.
        if self.is_superuser:
            self.role = self.Role.ADMIN
        super().save(*args, **kwargs)
