from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.exceptions import ApiError
from apps.common.permissions import IsVerified
from apps.listings.models import Listing
from apps.notifications.models import Notification
from apps.notifications.services import notify

from .models import Claim
from .serializers import ClaimSerializer, MyClaimSerializer


class ClaimCreateView(APIView):
    """POST /listings/{id}/claim — claim an OPEN listing (§9.6, FR-13).

    Conflict (409) if already claimed. On success the listing becomes CLAIMED
    and a chat thread opens.
    """

    permission_classes = [IsVerified]  # FR-2
    throttle_scope = "claim"           # §9.10: 30/day/user

    def post(self, request, listing_id):
        listing = get_object_or_404(Listing, pk=listing_id)
        if listing.author_id == request.user.id:
            raise ApiError("INVALID", "You cannot claim your own listing.")
        if listing.status != Listing.Status.OPEN:
            raise ApiError("ALREADY_CLAIMED", "Someone is already on this.",
                           status_code=status.HTTP_409_CONFLICT)
        try:
            with transaction.atomic():
                claim = Claim.objects.create(listing=listing, claimant=request.user)
                listing.status = Listing.Status.CLAIMED
                listing.save(update_fields=["status", "updated_at"])
        except IntegrityError:
            # Lost the race against the partial unique index.
            raise ApiError("ALREADY_CLAIMED", "Someone is already on this.",
                           status_code=status.HTTP_409_CONFLICT)

        ntype = (
            Notification.Type.REQUEST_CLAIMED
            if listing.type == Listing.Type.REQUEST
            else Notification.Type.OFFER_REQUESTED
        )
        notify(listing.author, ntype, context={"title": listing.title},
               data={"listing_id": str(listing.id), "claim_id": str(claim.id)})
        return Response(ClaimSerializer(claim).data, status=status.HTTP_201_CREATED)


class _ClaimActionView(APIView):
    permission_classes = [IsAuthenticated]

    def get_claim(self, claim_id):
        return get_object_or_404(
            Claim.objects.select_related("listing", "listing__author", "claimant"), pk=claim_id
        )


class ClaimWithdrawView(_ClaimActionView):
    """POST /claims/{id}/withdraw — claimant backs out → listing reverts to OPEN (FR-14)."""

    def post(self, request, claim_id):
        claim = self.get_claim(claim_id)
        if claim.claimant_id != request.user.id:
            raise ApiError("FORBIDDEN", "Only the claimant can withdraw.", status_code=403)
        if claim.status != Claim.Status.ACTIVE:
            raise ApiError("CONFLICT", "This claim is no longer active.", status_code=409)
        with transaction.atomic():
            claim.status = Claim.Status.WITHDRAWN
            claim.save(update_fields=["status"])
            claim.listing.status = Listing.Status.OPEN
            claim.listing.save(update_fields=["status", "updated_at"])
        return Response(ClaimSerializer(claim).data)


class ClaimDeliverView(_ClaimActionView):
    """POST /claims/{id}/deliver — the fulfilling party marks DELIVERED (FR-15)."""

    def post(self, request, claim_id):
        claim = self.get_claim(claim_id)
        if request.user.id != claim.fulfilling_user_id:
            raise ApiError("FORBIDDEN", "Only the fulfilling party can mark delivered.",
                           status_code=403)
        if claim.status != Claim.Status.ACTIVE or claim.listing.status != Listing.Status.CLAIMED:
            raise ApiError("CONFLICT", "Listing is not in a deliverable state.", status_code=409)
        with transaction.atomic():
            claim.delivered_at = timezone.now()
            claim.save(update_fields=["delivered_at"])
            claim.listing.status = Listing.Status.DELIVERED
            claim.listing.save(update_fields=["status", "updated_at"])
        notify_user = claim.receiving_user_id
        from apps.identity.models import User

        notify(User.objects.get(pk=notify_user), Notification.Type.CLAIM_DELIVERED,
               context={"title": claim.listing.title},
               data={"claim_id": str(claim.id)})
        return Response(ClaimSerializer(claim).data)


class ClaimConfirmView(_ClaimActionView):
    """POST /claims/{id}/confirm — receiving party confirms → COMPLETED, ratings unlock (FR-15)."""

    def post(self, request, claim_id):
        claim = self.get_claim(claim_id)
        if request.user.id != claim.receiving_user_id:
            raise ApiError("FORBIDDEN", "Only the receiving party can confirm.", status_code=403)
        if claim.listing.status != Listing.Status.DELIVERED:
            raise ApiError("CONFLICT", "Mark delivered before confirming.", status_code=409)
        with transaction.atomic():
            claim.status = Claim.Status.COMPLETED
            claim.completed_at = timezone.now()
            claim.save(update_fields=["status", "completed_at"])
            claim.listing.status = Listing.Status.COMPLETED
            claim.listing.save(update_fields=["status", "updated_at"])
            # §13.4: +3 trust per completed exchange to both parties.
            claim.claimant.adjust_trust(3)
            claim.listing.author.adjust_trust(3)
        from apps.identity.models import User

        notify(User.objects.get(pk=claim.fulfilling_user_id),
               Notification.Type.CLAIM_COMPLETED,
               context={"title": claim.listing.title}, data={"claim_id": str(claim.id)})
        return Response(ClaimSerializer(claim).data)


class MyClaimsView(APIView):
    """GET /me/claims?status=active|completed — claims made by the user (§9.6)."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = Claim.objects.filter(claimant=request.user).select_related(
            "listing", "listing__author"
        )
        if request.query_params.get("status"):
            qs = qs.filter(status=request.query_params["status"])
        from apps.common.pagination import CursorEnvelopePagination

        paginator = CursorEnvelopePagination()
        paginator.ordering = "-claimed_at"
        page = paginator.paginate_queryset(qs, request, view=self)
        return paginator.get_paginated_response(MyClaimSerializer(page, many=True).data)
