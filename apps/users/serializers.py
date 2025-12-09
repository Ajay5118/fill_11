from rest_framework import serializers
from django.contrib.auth import get_user_model, authenticate
from phonenumber_field.serializerfields import PhoneNumberField
from .models import OTP

User = get_user_model()


# ==========================================
# 1. BASIC USER SERIALIZERS
# ==========================================

class UserSerializer(serializers.ModelSerializer):
    """Basic User serializer for listing/displaying users"""

    class Meta:
        model = User
        fields = [
            'user_id', 'phone_number', 'full_name', 'email',
            'skill_level', 'primary_role', 'reliability_score',
            'no_shows', 'games_played', 'preferred_zone',
            'is_active', 'created_at'
        ]
        read_only_fields = ['user_id', 'reliability_score', 'no_shows', 'games_played', 'created_at']


class UserProfileSerializer(serializers.ModelSerializer):
    """Detailed profile view with all stats"""

    class Meta:
        model = User
        fields = [
            'user_id', 'phone_number', 'full_name', 'email',
            'skill_level', 'primary_role', 'reliability_score',
            'no_shows', 'games_played', 'preferred_zone',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'user_id', 'phone_number', 'reliability_score',
            'no_shows', 'games_played', 'created_at', 'updated_at'
        ]


class UpdateProfileSerializer(serializers.ModelSerializer):
    """Update user profile (limited fields)"""

    class Meta:
        model = User
        fields = ['full_name', 'email', 'skill_level', 'primary_role', 'preferred_zone']


# ==========================================
# 2. OTP SERIALIZERS
# ==========================================

class SendOTPSerializer(serializers.Serializer):
    """Request OTP for phone number"""
    phone_number = PhoneNumberField(region='IN')

    def validate_phone_number(self, value):
        """Ensure phone number format is correct"""
        if not value:
            raise serializers.ValidationError("Phone number is required")
        return value


class VerifyOTPSerializer(serializers.Serializer):
    """Verify OTP and login/register"""
    phone_number = PhoneNumberField(region='IN')
    otp = serializers.CharField(max_length=6, min_length=6)
    full_name = serializers.CharField(max_length=150, required=False, allow_blank=True)

    def validate(self, attrs):
        phone_number = attrs.get('phone_number')
        otp_code = attrs.get('otp')

        # Check if OTP exists and is valid
        try:
            otp_instance = OTP.objects.filter(
                phone_number=phone_number,
                otp=otp_code,
                is_verified=False
            ).latest('created_at')

            if not otp_instance.is_valid():
                raise serializers.ValidationError("OTP has expired or is invalid")

            # Mark OTP as verified
            otp_instance.is_verified = True
            otp_instance.save()

            attrs['otp_instance'] = otp_instance

        except OTP.DoesNotExist:
            raise serializers.ValidationError("Invalid OTP")

        return attrs


# ==========================================
# 3. TRADITIONAL REGISTRATION/LOGIN
# ==========================================

class UserRegistrationSerializer(serializers.ModelSerializer):
    """Traditional registration with password"""
    password = serializers.CharField(write_only=True, min_length=8, style={'input_type': 'password'})
    password_confirm = serializers.CharField(write_only=True, min_length=8, style={'input_type': 'password'})

    class Meta:
        model = User
        fields = [
            'phone_number', 'full_name', 'email', 'password', 'password_confirm',
            'skill_level', 'primary_role', 'preferred_zone'
        ]

    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({"password": "Passwords do not match"})
        return attrs

    def create(self, validated_data):
        validated_data.pop('password_confirm')
        password = validated_data.pop('password')

        user = User.objects.create_user(
            password=password,
            **validated_data
        )
        return user


class UserLoginSerializer(serializers.Serializer):
    """Traditional login with phone number and password"""
    phone_number = PhoneNumberField(region='IN')
    password = serializers.CharField(write_only=True, style={'input_type': 'password'})

    def validate(self, attrs):
        phone_number = attrs.get('phone_number')
        password = attrs.get('password')

        if phone_number and password:
            user = authenticate(
                request=self.context.get('request'),
                username=str(phone_number),
                password=password
            )

            if not user:
                raise serializers.ValidationError("Invalid credentials")

            if not user.is_active:
                raise serializers.ValidationError("User account is disabled")

            attrs['user'] = user
            return attrs
        else:
            raise serializers.ValidationError("Both phone number and password are required")


class ChangePasswordSerializer(serializers.Serializer):
    """Change password for authenticated user"""
    old_password = serializers.CharField(write_only=True, style={'input_type': 'password'})
    new_password = serializers.CharField(write_only=True, min_length=8, style={'input_type': 'password'})
    new_password_confirm = serializers.CharField(write_only=True, min_length=8, style={'input_type': 'password'})

    def validate_old_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError("Old password is incorrect")
        return value

    def validate(self, attrs):
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError({"new_password": "New passwords do not match"})
        return attrs