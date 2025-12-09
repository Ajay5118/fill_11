from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    SendOTPView,
    VerifyOTPView,
    UserRegistrationView,
    UserLoginView,
    UserLogoutView,
    UserProfileView,
    ChangePasswordView,
    UserViewSet,
    LeaderboardView,
    SearchUsersView,
)

app_name = 'users'

router = DefaultRouter()
router.register(r'all', UserViewSet, basename='user')

urlpatterns = [
    # OTP Authentication (Recommended)
    path('send-otp/', SendOTPView.as_view(), name='send-otp'),
    path('verify-otp/', VerifyOTPView.as_view(), name='verify-otp'),

    # Traditional Authentication (Password-based)
    path('register/', UserRegistrationView.as_view(), name='register'),
    path('login/', UserLoginView.as_view(), name='login'),
    path('logout/', UserLogoutView.as_view(), name='logout'),

    # Profile
    path('profile/', UserProfileView.as_view(), name='profile'),
    path('change-password/', ChangePasswordView.as_view(), name='change-password'),

    # Utility
    path('leaderboard/', LeaderboardView.as_view(), name='leaderboard'),
    path('search/', SearchUsersView.as_view(), name='search'),

    # ViewSet routes
    path('', include(router.urls)),
]