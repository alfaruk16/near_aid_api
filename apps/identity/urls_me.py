"""User & profile endpoints, mounted at /v1/ (§9.3)."""
from django.urls import path

from .views import DeviceView, MeView, PublicUserView, VerificationView

urlpatterns = [
    path("me", MeView.as_view(), name="me"),
    path("me/verification", VerificationView.as_view(), name="me-verification"),
    path("me/devices", DeviceView.as_view(), name="me-devices"),
    path("users/<uuid:user_id>", PublicUserView.as_view(), name="user-detail"),
]
