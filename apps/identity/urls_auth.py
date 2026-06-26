"""Auth endpoints, mounted at /v1/auth/ (§9.2)."""
from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import LogoutView, OTPRequestView, OTPVerifyView

urlpatterns = [
    path("otp/request", OTPRequestView.as_view(), name="otp-request"),
    path("otp/verify", OTPVerifyView.as_view(), name="otp-verify"),
    path("refresh", TokenRefreshView.as_view(), name="token-refresh"),
    path("logout", LogoutView.as_view(), name="logout"),
]
