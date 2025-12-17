from rest_framework import status, generics
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.authtoken.models import Token
from django.utils import timezone
from datetime import timedelta
import random
from phonenumber_field.phonenumber import PhoneNumber

from .models import OTP, User
from .serializers import (
    PhoneOTPRequestSerializer,
    OTPVerifySerializer,
    UserRegistrationSerializer,
    UserSerializer
)


@api_view(['POST'])
@permission_classes([AllowAny])
def generate_otp(request):
    """
    Generate and send OTP to phone number
    POST /api/auth/phone-otp/
    Body: {"phone": "+919876543210"}
    """
    serializer = PhoneOTPRequestSerializer(data=request.data)

    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    phone_str = serializer.validated_data['phone']

    # Convert string to PhoneNumber object
    phone_number = PhoneNumber.from_string(phone_str, region='IN')

    # Generate 6-digit OTP
    otp_code = str(random.randint(100000, 999999))

    # Set expiration time (10 minutes from now)
    expires_at = timezone.now() + timedelta(minutes=10)

    # Invalidate all previous unverified OTPs for this phone number
    OTP.objects.filter(
        phone_number=phone_number,
        is_verified=False,
        expires_at__gt=timezone.now()
    ).update(is_verified=True)

    # Create new OTP record
    otp_obj = OTP.objects.create(
        phone_number=phone_number,
        otp=otp_code,
        expires_at=expires_at,
        attempts=0,
    )

    # In production, send OTP via SMS service (Twilio, AWS SNS, etc.)
    # For now, we'll return it in response (remove in production!)
    print(f"OTP for {phone_number}: {otp_code}")  # Remove in production

    return Response({
        'message': 'OTP sent successfully',
        'phone': phone_str,
        'otp': otp_code,  # Remove this in production - only for testing
        'expires_in': 600,  # seconds
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([AllowAny])
def verify_otp(request):
    """
    Verify OTP and return token
    POST /api/auth/verify-otp/
    Body: {"phone": "+919876543210", "otp": "123456"}

    Returns:
    - If user exists: token and user data
    - If user doesn't exist: token and is_new_user flag (requires registration)
    """
    serializer = OTPVerifySerializer(data=request.data)

    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    phone_str = serializer.validated_data['phone']
    otp_obj = serializer.validated_data['otp_obj']

    # Convert string to PhoneNumber object
    phone_number = PhoneNumber.from_string(phone_str, region='IN')

    # Check if user already exists
    try:
        user = User.objects.get(phone=phone_number)
        # User exists, return login response
        token, created = Token.objects.get_or_create(user=user)

        return Response({
            'message': 'OTP verified successfully',
            'token': token.key,
            'is_new_user': False,
            'user': UserSerializer(user).data,
        }, status=status.HTTP_200_OK)

    except User.DoesNotExist:
        # User doesn't exist - create temporary user and return token
        # User must complete registration in the next step
        user = User.objects.create_user(phone=phone_number)
        token = Token.objects.create(user=user)

        return Response({
            'message': 'OTP verified successfully. Please complete registration.',
            'token': token.key,
            'is_new_user': True,
            'phone': phone_str,
        }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def complete_registration(request):
    """
    Complete user registration after OTP verification
    POST /api/auth/register/
    Headers: Authorization: Token <token>
    Body: {
        "name": "John Doe",  // required
        "age": 25,  // required
        "skill_level": "BEGINNER",  // required (BEGINNER, INTERMEDIATE, SERIOUS)
        "skill_role": "BATSMAN",  // required (BATSMAN, BOWLER, WICKET_KEEPER, ALL_ROUNDER, ANY)
        "pin_code": "500001",  // required
        "email": "john@example.com"  // optional
    }
    """
    user = request.user

    # Check if user has already completed registration (has a name)
    if user.name:
        return Response({
            'message': 'User already registered',
            'user': UserSerializer(user).data
        }, status=status.HTTP_400_BAD_REQUEST)

    serializer = UserRegistrationSerializer(instance=user, data=request.data, partial=False)

    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    serializer.save()

    return Response({
        'message': 'Registration completed successfully',
        'user': UserSerializer(user).data,
    }, status=status.HTTP_201_CREATED)


class UserProfileView(generics.RetrieveUpdateAPIView):
    """Get and update user profile"""
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user