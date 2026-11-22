from django.contrib.auth.models import AbstractUser
from django.db import models
from .validators import validate_phone_number

class User(AbstractUser):
    ROLE_CHOICES = (
        ('CUSTOMER', 'Customer'),
        ('PHARMACY', 'Pharmacy Owner'),
        ('ADMIN', 'Administrator'),
    )
    
    email = models.EmailField(unique=True, verbose_name="Email Address")
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='CUSTOMER', db_index=True)
    phone_number = models.CharField(max_length=20, blank=True, validators=[validate_phone_number])
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['role', '-date_joined'], name='user_role_joined_idx'),
        ]

    @property
    def is_customer(self):
        return self.role == 'CUSTOMER'
        
    @property
    def is_pharmacy_owner(self):
        return self.role == 'PHARMACY'
        
    @property
    def is_admin_user(self):
        # Review N16: is_staff alone (Django admin access) no longer grants the app admin portal.
        return self.role == 'ADMIN' or self.is_superuser

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"
