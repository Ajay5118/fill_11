import uuid
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.utils.translation import gettext_lazy as _
from phonenumber_field.modelfields import PhoneNumberField
from django.utils import timezone
from datetime import timedelta
import random


# ==========================================
# 1. ENUMS (Choices)
# ==========================================

class SkillLevel(models.TextChoices):
    BEGINNER = 'BEGINNER', _('Beginner')
    INTERMEDIATE = 'INTERMEDIATE', _('Intermediate')
    PRO = 'PRO', _('Pro')


class PlayerRole(models.TextChoices):
    BATSMAN = 'BATSMAN', _('Batsman')
    BOWLER = 'BOWLER', _('Bowler')
    ALL_ROUNDER = 'ALL_ROUNDER', _('All Rounder')
    WICKET_KEEPER = 'WICKET_KEEPER', _('Wicket Keeper')
    ANY = 'ANY', _('Any Role')


# ==========================================
# 2. ABSTRACT BASE MODEL
# ==========================================

class BaseModel(models.Model):
    """
    Abstract base model that provides self-updating
    'created_at' and 'updated_at' fields.
    """
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


# ==========================================
# 3. USER MANAGER
# ==========================================

class UserManager(BaseUserManager):
    """Custom manager for the custom User model."""

    def create_user(self, phone_number, password=None, **extra_fields):
        if not phone_number:
            raise ValueError('Users must have a phone number')

        user = self.model(phone_number=phone_number, **extra_fields)
        if password:
            user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, phone_number, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(phone_number, password, **extra_fields)


# ==========================================
# 4. USER MODEL
# ==========================================

class User(AbstractBaseUser, PermissionsMixin, BaseModel):
    # IDs & Auth
    user_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    phone_number = PhoneNumberField(unique=True, region='IN')
    full_name = models.CharField(max_length=150)
    email = models.EmailField(unique=True, blank=True, null=True)

    # Cricket Profile
    skill_level = models.CharField(max_length=20, choices=SkillLevel.choices, default=SkillLevel.BEGINNER)
    primary_role = models.CharField(max_length=20, choices=PlayerRole.choices, default=PlayerRole.ALL_ROUNDER)

    # Trust Metrics
    reliability_score = models.DecimalField(max_digits=3, decimal_places=1, default=5.0)
    no_shows = models.PositiveIntegerField(default=0)
    games_played = models.PositiveIntegerField(default=0)

    # Location Targeting
    preferred_zone = models.CharField(max_length=100, blank=True, help_text="e.g. Gachibowli")

    # System Fields
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    objects = UserManager()

    USERNAME_FIELD = 'phone_number'
    REQUIRED_FIELDS = ['full_name']

    def __str__(self):
        return f"{self.full_name} ({self.phone_number})"


# ==========================================
# 5. OTP MODEL
# ==========================================

class OTP(BaseModel):
    """Store OTP for phone number verification"""
    phone_number = PhoneNumberField(region='IN')
    otp = models.CharField(max_length=6)
    is_verified = models.BooleanField(default=False)
    expires_at = models.DateTimeField()

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"OTP for {self.phone_number}"

    @staticmethod
    def generate_otp():
        """Generate a 6-digit OTP"""
        return str(random.randint(100000, 999999))

    def is_valid(self):
        """Check if OTP is still valid (not expired)"""
        return timezone.now() < self.expires_at and not self.is_verified

    @classmethod
    def create_otp(cls, phone_number):
        """Create a new OTP for a phone number"""
        otp_code = cls.generate_otp()
        expires_at = timezone.now() + timedelta(minutes=5)  # 5 minutes validity

        # Invalidate previous OTPs for this phone number
        cls.objects.filter(phone_number=phone_number, is_verified=False).delete()

        otp_instance = cls.objects.create(
            phone_number=phone_number,
            otp=otp_code,
            expires_at=expires_at
        )
        return otp_instance


# ==========================================
# 6. TEAM MODEL
# ==========================================

class Team(BaseModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    captain = models.ForeignKey(User, on_delete=models.CASCADE, related_name='captained_teams')
    team_name = models.CharField(max_length=100, blank=True, null=True)
    temp_player_count = models.PositiveIntegerField(default=0)

    def __str__(self):
        return self.team_name or f"{self.captain.full_name}'s Squad"