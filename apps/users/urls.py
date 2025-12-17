from django.urls import path
from . import views

app_name = 'users'

urlpatterns = [
    path('phone-otp/', views.generate_otp, name='generate-otp'),
    path('send-otp/', views.generate_otp, name='send-otp'),
    path('verify-otp/', views.verify_otp, name='verify-otp'),
    path('register/', views.complete_registration, name='complete-registration'),
    path('profile/', views.UserProfileView.as_view(), name='user-profile'),
]

