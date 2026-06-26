"""Ratings (§9.8). Mounted at /v1/."""
from django.urls import path

from .views import RatingCreateView, UserRatingsView

urlpatterns = [
    path("claims/<uuid:claim_id>/rating", RatingCreateView.as_view(), name="claim-rating"),
    path("users/<uuid:user_id>/ratings", UserRatingsView.as_view(), name="user-ratings"),
]
