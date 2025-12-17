from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from phonenumber_field.modelfields import PhoneNumberField
import uuid


class UserManager(BaseUserManager):
    """Custom user manager for phone-based authentication"""

    def create_user(self, phone, password=None, **extra_fields):
        if not phone:
            raise ValueError('The Phone field must be set')

        user = self.model(phone=phone, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, phone, name, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        if password is None:
            raise ValueError("Superuser must have a password.")

        user = self.model(phone=phone, name=name or '', **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user


class User(AbstractUser):
    """Custom User model extending AbstractUser"""
    user_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    phone = PhoneNumberField(unique=True, region='IN')
    name = models.CharField(max_length=150, blank=True, default='')
    email = models.EmailField(blank=True, null=True, unique=True)  # Optional
    
    SKILL_LEVEL_CHOICES = [
        ('BEGINNER', 'Beginner'),
        ('INTERMEDIATE', 'Intermediate'),
        ('SERIOUS', 'Serious'),
    ]
    skill_level = models.CharField(max_length=20, choices=SKILL_LEVEL_CHOICES, default='BEGINNER')
    SKILL_ROLE_CHOICES = [
        ('BATSMAN', 'Batsman'),
        ('BOWLER', 'Bowler'),
        ('WICKET_KEEPER', 'Wicket Keeper'),
        ('ALL_ROUNDER', 'All Rounder'),
        ('ANY', 'Any Role'),
    ]
    skill_role = models.CharField(max_length=20, choices=SKILL_ROLE_CHOICES, default='ANY')
    # Primary role the user prefers to play in matches
    primary_role = models.CharField(max_length=20, choices=SKILL_ROLE_CHOICES, default='ANY')
    # Gig economy fields
    is_open_for_gigs = models.BooleanField(default=False)
    hourly_rate = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    practice_role = models.CharField(max_length=20, choices=SKILL_ROLE_CHOICES, blank=True, default='')
    # Basic profile fields
    age = models.PositiveIntegerField(null=True, blank=True)
    pin_code = models.CharField(max_length=10, blank=True, default='')
    skill_video = models.FileField(upload_to='skill_videos/', blank=True, null=True)
    # Ratings & stats
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=5.00)
    reliability_score = models.DecimalField(max_digits=3, decimal_places=2, default=5.00)
    wallet_balance = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    is_video_verified = models.BooleanField(default=False)
    total_runs = models.PositiveIntegerField(default=0)
    total_wickets = models.PositiveIntegerField(default=0)
    matches_played = models.PositiveIntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Override username to use phone instead
    username = None
    USERNAME_FIELD = 'phone'
    REQUIRED_FIELDS = []
    
    objects = UserManager()
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'User'
        verbose_name_plural = 'Users'
    
    def __str__(self):
        display_name = self.name or str(self.phone)
        return f"{display_name} ({self.phone})"


class OTP(models.Model):
    """OTP model for phone authentication"""
    phone_number = PhoneNumberField(region='IN')
    otp = models.CharField(max_length=6)
    is_verified = models.BooleanField(default=False)
    expires_at = models.DateTimeField()
    attempts = models.PositiveIntegerField(default=0)
    full_name = models.CharField(max_length=150, blank=True)  # For registration
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'OTP'
        verbose_name_plural = 'OTPs'
    
    def __str__(self):
        return f"OTP for {self.phone_number} - {self.otp}"
