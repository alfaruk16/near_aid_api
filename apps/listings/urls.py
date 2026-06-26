"""Listings, categories & discovery (§9.4, §9.5). Mounted at /v1/."""
from django.urls import path

from .views import (
    CategoryListView,
    ListingCancelView,
    ListingDetailView,
    ListingListCreateView,
    ListingNearbyView,
    MyListingsView,
)

urlpatterns = [
    path("categories", CategoryListView.as_view(), name="categories"),
    # Order matters: literal paths before the <uuid> capture.
    path("listings/nearby", ListingNearbyView.as_view(), name="listings-nearby"),
    path("listings", ListingListCreateView.as_view(), name="listings"),
    path("listings/<uuid:listing_id>", ListingDetailView.as_view(), name="listing-detail"),
    path("listings/<uuid:listing_id>/cancel", ListingCancelView.as_view(), name="listing-cancel"),
    path("me/listings", MyListingsView.as_view(), name="me-listings"),
    # Legacy aliases bound to type=request (§9.5).
    path("requests/nearby", ListingNearbyView.as_view(), name="requests-nearby"),
]
