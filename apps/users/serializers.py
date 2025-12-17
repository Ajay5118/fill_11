from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.utils import timezone
from phonenumber_field.phonenumber import PhoneNumber
from .models import OTP

User = get_user_model()


class PhoneOTPRequestSerializer(serializers.Serializer):
    """Serializer for requesting OTP - only phone required"""
    phone = serializers.CharField(required=True)

    def validate_phone(self, value):
        """Validate phone number format"""
        # Normalize phone number
        if not value.startswith('+'):
            # Add country code if not present
            if value.startswith('0'):
                value = '+91' + value[1:]
            elif len(value) == 10:
                value = '+91' + value
            else:
                value = '+91' + value

        # Validate using phonenumbers library
        try:
            phone_number = PhoneNumber.from_string(value, region='IN')
            if not phone_number.is_valid():
                raise serializers.ValidationError("Invalid phone number format")
            return str(phone_number)
        except Exception:
            raise serializers.ValidationError("Invalid phone number format")


class OTPVerifySerializer(serializers.Serializer):
    """Serializer for verifying OTP"""
    phone = serializers.CharField(required=True)
    otp = serializers.CharField(required=True, max_length=6, min_length=6)

    def validate_phone(self, value):
        """Validate phone number format"""
        # Normalize phone number
        if not value.startswith('+'):
            # Add country code if not present
            if value.startswith('0'):
                value = '+91' + value[1:]
            elif len(value) == 10:
                value = '+91' + value
            else:
                value = '+91' + value

        # Validate using phonenumbers library
        try:
            phone_number = PhoneNumber.from_string(value, region='IN')
            if not phone_number.is_valid():
                raise serializers.ValidationError("Invalid phone number format")
            return str(phone_number)
        except Exception:
            raise serializers.ValidationError("Invalid phone number format")

    def validate(self, attrs):
        """Validate OTP"""
        phone_str = attrs['phone']
        otp = attrs['otp']

        # Convert string to PhoneNumber object for query
        phone_number = PhoneNumber.from_string(phone_str, region='IN')

        # Find the most recent unverified OTP for this phone
        otp_obj = OTP.objects.filter(
            phone_number=phone_number,
            is_verified=False,
            expires_at__gt=timezone.now()
        ).order_by('-created_at').first()

        if not otp_obj:
            raise serializers.ValidationError({
                'otp': 'No valid OTP found. Please request a new OTP.'
            })

        # Check attempts
        if otp_obj.attempts >= 5:
            raise serializers.ValidationError({
                'otp': 'Maximum OTP verification attempts exceeded. Please request a new OTP.'
            })

        # Verify OTP
        if otp_obj.otp != otp:
            otp_obj.attempts += 1
            otp_obj.save()
            remaining_attempts = 5 - otp_obj.attempts
            raise serializers.ValidationError({
                'otp': f'Invalid OTP. {remaining_attempts} attempts remaining.'
            })

        # Mark OTP as verified
        otp_obj.is_verified = True
        otp_obj.save()

        attrs['otp_obj'] = otp_obj
        return attrs


class UserRegistrationSerializer(serializers.ModelSerializer):
    """Serializer for completing user registration - only email is optional"""

    # Make email optional, all others required
    email = serializers.EmailField(required=False, allow_blank=True, allow_null=True)

    class Meta:
        model = User
        fields = [
            'name', 'email', 'age', 'skill_level',
            'skill_role', 'pin_code'
        ]
        extra_kwargs = {
            'name': {'required': True},
            'age': {'required': True},
            'skill_level': {'required': True},
            'skill_role': {'required': True},
            'pin_code': {'required': True},
        }

    def validate_name(self, value):
        """Ensure name is provided and not empty"""
        if not value or not value.strip():
            raise serializers.ValidationError("Name is required")
        return value.strip()

    def validate_email(self, value):
        """Validate email if provided"""
        if value:
            # Check if email already exists for another user
            if User.objects.filter(email=value).exclude(user_id=self.instance.user_id).exists():
                raise serializers.ValidationError("Email already exists")
        return value

    def validate_pin_code(self, value):
        """Validate pin code"""
        if not value or not value.strip():
            raise serializers.ValidationError("Pin code is required")
        return value.strip()


class UserSerializer(serializers.ModelSerializer):
    """Serializer for User model"""
    phone = serializers.CharField(source='phone.as_e164', read_only=True)

    class Meta:
        model = User
        fields = [
            'user_id', 'phone', 'name', 'email', 'age',
            'skill_level', 'skill_role', 'primary_role',
            'pin_code', 'is_open_for_gigs', 'hourly_rate', 'practice_role',
            'rating', 'reliability_score', 'wallet_balance', 'is_video_verified',
            'total_runs', 'total_wickets', 'matches_played',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'user_id', 'phone', 'created_at', 'updated_at',
            'rating', 'reliability_score', 'wallet_balance', 'is_video_verified',
            'total_runs', 'total_wickets', 'matches_played'
        ]