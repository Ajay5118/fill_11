from rest_framework import generics, viewsets, status, permissions, filters
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.authtoken.models import Token
from django.contrib.auth import get_user_model
from .serializers import (
    UserSerializer,
    UserRegistrationSerializer,
    UserLoginSerializer,
    ChangePasswordSerializer,
    UserProfileSerializer,
    UpdateProfileSerializer,
    SendOTPSerializer,
    VerifyOTPSerializer
)
from .models import OTP

User = get_user_model()


# ==========================================
# 1. OTP AUTHENTICATION VIEWS
# ==========================================

class SendOTPView(generics.GenericAPIView):
    """
    Endpoint: POST /api/users/send-otp/
    Body: {"phone_number": "+919876543210"}
    Logic: Generates and sends OTP to the phone number
    """
    serializer_class = SendOTPSerializer
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        phone_number = serializer.validated_data['phone_number']

        # Create OTP
        otp_instance = OTP.create_otp(phone_number)

        # TODO: Send OTP via SMS (integrate with SMS provider)
        # For now, we'll return it in response (ONLY FOR DEVELOPMENT)
        # In production, remove the otp from response

        print(f"OTP for {phone_number}: {otp_instance.otp}")  # For development

        return Response({
            "message": "OTP sent successfully",
            "phone_number": str(phone_number),
            "otp": otp_instance.otp,  # REMOVE THIS IN PRODUCTION
            "expires_in": "5 minutes"
        }, status=status.HTTP_200_OK)


class VerifyOTPView(generics.GenericAPIView):
    """
    Endpoint: POST /api/users/verify-otp/
    Body: {
        "phone_number": "+919876543210",
        "otp": "123456",
        "full_name": "Rahul Sharma"  // Required only for new users
    }
    Logic: Verifies OTP and logs in user. Creates new user if doesn't exist.
    """
    serializer_class = VerifyOTPSerializer
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        phone_number = serializer.validated_data['phone_number']
        full_name = serializer.validated_data.get('full_name', '')

        # Check if user exists
        user, created = User.objects.get_or_create(
            phone_number=phone_number,
            defaults={
                'full_name': full_name or str(phone_number),
                'is_active': True
            }
        )

        # If user was just created but no name provided, raise error
        if created and not full_name:
            user.delete()
            return Response({
                "error": "full_name is required for new users"
            }, status=status.HTTP_400_BAD_REQUEST)

        # Generate or retrieve token
        token, _ = Token.objects.get_or_create(user=user)

        return Response({
            "token": token.key,
            "user": UserSerializer(user).data,
            "message": "Login successful" if not created else "Registration successful"
        }, status=status.HTTP_200_OK if not created else status.HTTP_201_CREATED)


# ==========================================
# 2. TRADITIONAL AUTHENTICATION VIEWS
# ==========================================

class UserRegistrationView(generics.CreateAPIView):
    """
    Endpoint: POST /api/users/register/
    Logic: Creates a new user with password
    """
    queryset = User.objects.all()
    serializer_class = UserRegistrationSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        token, created = Token.objects.get_or_create(user=user)

        return Response({
            "user": UserSerializer(user).data,
            "token": token.key,
            "message": "Registration Successful"
        }, status=status.HTTP_201_CREATED)


class UserLoginView(generics.GenericAPIView):
    """
    Endpoint: POST /api/users/login/
    Logic: Login with phone number and password
    """
    serializer_class = UserLoginSerializer
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.validated_data['user']
        token, created = Token.objects.get_or_create(user=user)

        return Response({
            "token": token.key,
            "user_id": str(user.user_id),
            "full_name": user.full_name,
            "phone_number": str(user.phone_number),
            "reliability_score": str(user.reliability_score)
        }, status=status.HTTP_200_OK)


class UserLogoutView(APIView):
    """
    Endpoint: POST /api/users/logout/
    Logic: Deletes the user's Token
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        try:
            request.user.auth_token.delete()
        except (AttributeError, Token.DoesNotExist):
            pass

        return Response({"message": "Logged out successfully"}, status=status.HTTP_200_OK)


# ==========================================
# 3. PROFILE MANAGEMENT
# ==========================================

class UserProfileView(generics.RetrieveUpdateAPIView):
    """
    Endpoint: GET/PUT/PATCH /api/users/profile/
    Logic: Get or Update the current logged-in user's details
    """
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user

    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return UpdateProfileSerializer
        return UserProfileSerializer


class ChangePasswordView(generics.UpdateAPIView):
    """
    Endpoint: PUT /api/users/change-password/
    Logic: Changes password
    """
    serializer_class = ChangePasswordSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user

    def update(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = request.user
        user.set_password(serializer.validated_data['new_password'])
        user.save()

        # Invalidate old token and create new one
        Token.objects.filter(user=user).delete()
        token = Token.objects.create(user=user)

        return Response({
            "message": "Password updated successfully",
            "token": token.key
        }, status=status.HTTP_200_OK)


# ==========================================
# 4. UTILITY VIEWS (Leaderboard & Search)
# ==========================================

class LeaderboardView(generics.ListAPIView):
    """
    Endpoint: GET /api/users/leaderboard/
    Logic: Returns top 50 users sorted by reliability score
    """
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return User.objects.filter(is_active=True).order_by('-reliability_score', 'no_shows')[:50]


class SearchUsersView(generics.ListAPIView):
    """
    Endpoint: GET /api/users/search/?search=Rahul
    Logic: Find players by Name or Phone Number
    """
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = User.objects.filter(is_active=True)
    filter_backends = [filters.SearchFilter]
    search_fields = ['full_name', 'phone_number']


# ==========================================
# 5. VIEWSET (For Admin/General Access)
# ==========================================

class UserViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Endpoint: GET /api/users/
    Logic: Read-only view of all users
    """
    queryset = User.objects.filter(is_active=True)
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter]
    search_fields = ['full_name', 'phone_number']