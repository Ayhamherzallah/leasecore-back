from django.db import models
from django.contrib.auth.models import User

class Role(models.TextChoices):
    SUPER_ADMIN = 'SUPER_ADMIN', 'Super Admin'
    BUILDING_MANAGER = 'BUILDING_MANAGER', 'Building Manager'
    ACCOUNTANT = 'ACCOUNTANT', 'Accountant'
    MANAGER = 'MANAGER', 'Manager'

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.BUILDING_MANAGER)
    buildings = models.ManyToManyField('properties.Building', blank=True, related_name='assigned_users')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} ({self.role})"
