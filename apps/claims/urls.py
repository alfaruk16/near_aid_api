"""Claims (§9.6). Mounted at /v1/."""
from django.urls import path

from .views import (
    ClaimConfirmView,
    ClaimCreateView,
    ClaimDeliverView,
    ClaimWithdrawView,
    MyClaimsView,
)

urlpatterns = [
    path("listings/<uuid:listing_id>/claim", ClaimCreateView.as_view(), name="listing-claim"),
    path("claims/<uuid:claim_id>/withdraw", ClaimWithdrawView.as_view(), name="claim-withdraw"),
    path("claims/<uuid:claim_id>/deliver", ClaimDeliverView.as_view(), name="claim-deliver"),
    path("claims/<uuid:claim_id>/confirm", ClaimConfirmView.as_view(), name="claim-confirm"),
    path("me/claims", MyClaimsView.as_view(), name="me-claims"),
]
