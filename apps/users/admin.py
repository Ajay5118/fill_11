from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, OTP


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Admin configuration for User model"""
    list_display = ['phone', 'name', 'skill_level', 'rating', 'wallet_balance', 'is_video_verified', 'created_at']
    list_filter = ['skill_level', 'is_video_verified', 'is_active', 'is_staff']
    search_fields = ['phone', 'name']
    ordering = ['-created_at']
    
    fieldsets = (
        (None, {'fields': ('phone', 'name')}),
        ('Skills', {'fields': ('skill_level', 'skill_video', 'is_video_verified', 'rating')}),
        ('Wallet', {'fields': ('wallet_balance',)}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'created_at', 'updated_at')}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('phone', 'name', 'skill_level'),
        }),
    )
    
    readonly_fields = ['created_at', 'updated_at', 'last_login']


@admin.register(OTP)
class OTPAdmin(admin.ModelAdmin):
    """Admin configuration for OTP model"""
    list_display = ['phone_number', 'otp', 'is_verified', 'attempts', 'expires_at', 'created_at']
    list_filter = ['is_verified', 'created_at']
    search_fields = ['phone_number']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['-created_at']

