# apps/matches/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import MatchViewSet, VacancyViewSet, VenueViewSet, EscrowTransactionViewSet

app_name = 'matches'

router = DefaultRouter()
router.register(r'matches', MatchViewSet, basename='match')
router.register(r'vacancies', VacancyViewSet, basename='vacancy')
router.register(r'venues', VenueViewSet, basename='venue')
router.register(r'escrow', EscrowTransactionViewSet, basename='escrow')

urlpatterns = [
    path('', include(router.urls)),
]

# ==================== apps/matches/permissions.py ====================

from rest_framework import permissions


class IsMatchCaptainOrReadOnly(permissions.BasePermission):
    """
    Custom permission to only allow captains of a match to edit it.
    """

    def has_object_permission(self, request, view, obj):
        # Read permissions are allowed to any request
        if request.method in permissions.SAFE_METHODS:
            return True

        # Write permissions are only allowed to the captain
        return obj.host_team.captain == request.user


class IsVacancyMatchCaptain(permissions.BasePermission):
    """
    Custom permission for vacancy operations - only match captain can edit
    """

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True

        # obj is a Vacancy, check its match's captain
        return obj.match.host_team.captain == request.user


class IsParticipantOrCaptain(permissions.BasePermission):
    """
    Permission for match participants or captain
    """

    def has_object_permission(self, request, view, obj):
        # Check if user is the captain
        if obj.host_team.captain == request.user:
            return True

        # Check if user is a participant (has escrow transaction)
        from .models import EscrowTransaction
        return EscrowTransaction.objects.filter(
            match=obj,
            payer=request.user
        ).exists()


# ==================== apps/users/serializers.py ====================

# Basic User serializer for the users app
from rest_framework import serializers
from django.contrib.auth import get_user_model

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    """Complete user serializer"""

    class Meta:
        model = User
        fields = [
            'user_id', 'full_name', 'phone_number', 'email',
            'skill_level', 'primary_role', 'reliability_score',
            'no_shows', 'preferred_zone', 'is_active',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'user_id', 'reliability_score', 'no_shows',
            'created_at', 'updated_at'
        ]
        extra_kwargs = {
            'phone_number': {'required': True},
            'password': {'write_only': True}
        }

    def validate_phone_number(self, value):
        """Validate phone number format"""
        import re
        # Basic validation for Indian phone numbers
        if not re.match(r'^[6-9]\d{9}$', value):
            raise serializers.ValidationError(
                "Invalid phone number format. Must be a 10-digit Indian mobile number."
            )
        return value


class UserRegistrationSerializer(serializers.ModelSerializer):
    """User registration serializer"""
    password = serializers.CharField(write_only=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = [
            'full_name', 'phone_number', 'email', 'password',
            'password_confirm', 'skill_level', 'primary_role', 'preferred_zone'
        ]

    def validate(self, data):
        """Validate passwords match"""
        if data['password'] != data['password_confirm']:
            raise serializers.ValidationError({"password": "Passwords do not match"})
        return data

    def create(self, validated_data):
        """Create user with hashed password"""
        validated_data.pop('password_confirm')
        password = validated_data.pop('password')
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user


class UserProfileSerializer(serializers.ModelSerializer):
    """User profile with stats"""
    total_matches_played = serializers.SerializerMethodField()
    escrow_balance = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'user_id', 'full_name', 'phone_number', 'email',
            'skill_level', 'primary_role', 'reliability_score',
            'no_shows', 'preferred_zone', 'total_matches_played',
            'escrow_balance'
        ]
        read_only_fields = fields

    def get_total_matches_played(self, obj):
        """Count matches where user has checked in"""
        from apps.matches.models import GroundCheckin
        return GroundCheckin.objects.filter(
            user=obj,
            is_successful=True
        ).count()

    def get_escrow_balance(self, obj):
        """Calculate total amount in escrow"""
        from apps.matches.models import EscrowTransaction
        from django.db.models import Sum

        total = EscrowTransaction.objects.filter(
            payer=obj,
            status='HELD'
        ).aggregate(Sum('amount'))['amount__sum']

        return float(total) if total else 0.0


# ==================== EXAMPLE USAGE IN config/urls.py ====================

"""
# In your main urls.py (config/urls.py):

from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/users/', include('apps.users.urls')),
    path('api/', include('apps.matches.urls')),
    # Or if you want versioning:
    # path('api/v1/users/', include('apps.users.urls')),
    # path('api/v1/', include('apps.matches.urls')),
]
"""

# ==================== EXAMPLE API ENDPOINTS ====================

"""
AVAILABLE ENDPOINTS:

MATCHES:
- GET    /api/matches/                          - List all matches
- POST   /api/matches/                          - Create match
- GET    /api/matches/{id}/                     - Match detail
- PUT    /api/matches/{id}/                     - Update match
- DELETE /api/matches/{id}/                     - Delete match
- POST   /api/matches/{id}/add_vacancy/         - Add vacancy (captain only)
- POST   /api/matches/{id}/join_vacancy/        - Join vacancy
- POST   /api/matches/{id}/gps_checkin/         - GPS check-in
- GET    /api/matches/{id}/my_participation/    - Check participation
- POST   /api/matches/{id}/cancel_match/        - Cancel match (captain only)

VACANCIES:
- GET    /api/vacancies/                        - List vacancies
- POST   /api/vacancies/                        - Create vacancy
- GET    /api/vacancies/{id}/                   - Vacancy detail
- PUT    /api/vacancies/{id}/                   - Update vacancy
- DELETE /api/vacancies/{id}/                   - Delete vacancy

VENUES:
- GET    /api/venues/                           - List venues
- POST   /api/venues/                           - Create venue
- GET    /api/venues/{id}/                      - Venue detail
- GET    /api/venues/nearby/?lat=17.44&long=78.39&radius=5  - Nearby venues

ESCROW:
- GET    /api/escrow/                           - List user's transactions
- GET    /api/escrow/{id}/                      - Transaction detail

QUERY PARAMETERS:
- /api/matches/?upcoming=true                   - Only upcoming matches
- /api/matches/?ground_status=SECURED          - Filter by status
- /api/matches/?venue_id={uuid}                - Filter by venue
- /api/vacancies/?status=OPEN                  - Filter by status
- /api/vacancies/?match_id={uuid}              - Filter by match
- /api/vacancies/?only_open=true               - Only open vacancies
"""