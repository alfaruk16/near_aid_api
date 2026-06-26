from decimal import Decimal

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.claims.models import Claim
from apps.common.exceptions import ApiError
from apps.common.pagination import CursorEnvelopePagination
from apps.identity.models import User
from apps.notifications.models import Notification
from apps.notifications.services import notify

from .models import Rating
from .serializers import RatingCreateSerializer, RatingSerializer


class RatingCreateView(APIView):
    """POST /claims/{id}/rating — rate the counterpart after COMPLETED (§9.8, FR-20)."""

    permission_classes = [IsAuthenticated]

    def post(self, request, claim_id):
        claim = get_object_or_404(
            Claim.objects.select_related("listing", "listing__author", "claimant"), pk=claim_id
        )
        if request.user.id not in (claim.claimant_id, claim.listing.author_id):
            raise ApiError("FORBIDDEN", "You are not part of this exchange.", status_code=403)
        if claim.status != Claim.Status.COMPLETED:
            raise ApiError("CONFLICT", "You can rate only after the exchange is completed.",
                           status_code=409)
        if Rating.objects.filter(claim=claim, rater=request.user).exists():
            raise ApiError("CONFLICT", "You have already rated this exchange.", status_code=409)

        ser = RatingCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        ratee_id = claim.listing.author_id if request.user.id == claim.claimant_id else claim.claimant_id
        ratee = User.objects.get(pk=ratee_id)
        rating = Rating.objects.create(
            claim=claim, rater=request.user, ratee=ratee,
            score=ser.validated_data["score"], comment=ser.validated_data["comment"],
        )
        # §13.4: trust adjusts by (rating − 3) × 2 per received rating.
        ratee.adjust_trust((Decimal(rating.score) - 3) * 2)
        notify(ratee, Notification.Type.NEW_RATING,
               context={"title": f"{rating.score}★ from {request.user.display_name or 'a neighbour'}"},
               data={"claim_id": str(claim.id)})
        return Response(RatingSerializer(rating).data, status=status.HTTP_201_CREATED)


class UserRatingsView(APIView):
    """GET /users/{id}/ratings — public ratings list for a user (§9.8)."""

    permission_classes = [IsAuthenticated]

    def get(self, request, user_id):
        user = get_object_or_404(User, pk=user_id)
        qs = user.ratings_received.select_related("rater")
        paginator = CursorEnvelopePagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        return paginator.get_paginated_response(RatingSerializer(page, many=True).data)
