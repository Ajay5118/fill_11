from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth import get_user_model
from .models import OTP, Team

User = get_user_model()


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Custom User Admin"""
    list_display = [
        'phone_number', 'full_name', 'skill_level', 'primary_role',
        'reliability_score', 'no_shows', 'games_played', 'is_active', 'created_at'
    ]

    list_filter = [
        'skill_level', 'primary_role', 'is_active',
        'preferred_zone', 'created_at'
    ]

    search_fields = ['phone_number', 'full_name', 'email']
    ordering = ['-created_at']
    readonly_fields = ['user_id', 'created_at', 'updated_at', 'reliability_score']

    fieldsets = (
        ('Basic Info', {
            'fields': ('user_id', 'full_name', 'phone_number', 'email', 'password')
        }),
        ('Cricket Profile', {
            'fields': ('skill_level', 'primary_role', 'preferred_zone')
        }),
        ('Statistics', {
            'fields': ('reliability_score', 'no_shows', 'games_played')
        }),
        ('Permissions', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': (
                'phone_number', 'full_name', 'email', 'password1', 'password2',
                'skill_level', 'primary_role', 'preferred_zone', 'is_active', 'is_staff'
            ),
        }),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related()


@admin.register(OTP)
class OTPAdmin(admin.ModelAdmin):
    """OTP Admin Panel"""
    list_display = ['phone_number', 'otp', 'is_verified', 'expires_at', 'created_at']
    list_filter = ['is_verified', 'created_at']
    search_fields = ['phone_number']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['-created_at']


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    """Team Admin Panel"""
    list_display = ['team_name', 'captain', 'temp_player_count', 'created_at']
    list_filter = ['created_at']
    search_fields = ['team_name', 'captain__full_name']
    readonly_fields = ['id', 'created_at', 'updated_at']
    ordering = ['-created_at']