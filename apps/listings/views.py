import base64

from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.geos import Point
from django.contrib.gis.measure import D
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.exceptions import ApiError
from apps.common.geo import distance_band
from apps.common.permissions import IsVerified
from apps.safety.models import Block

from .models import Category, Listing
from .serializers import (
    CategorySerializer,
    ListingCardSerializer,
    ListingCreateSerializer,
    ListingDetailSerializer,
    ListingEditSerializer,
)


class CategoryListView(APIView):
    """GET /categories (§9.4)."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = Category.objects.filter(is_active=True)
        return Response({"results": CategorySerializer(qs, many=True).data})


def _blocked_user_ids(user):
    """Ids the user blocked or who blocked them — hidden from each other's feeds (FR-22)."""
    out = set(Block.objects.filter(blocker=user).values_list("blocked_id", flat=True))
    out |= set(Block.objects.filter(blocked=user).values_list("blocker_id", flat=True))
    return out


class ListingListCreateView(APIView):
    """POST /listings — create (§9.5). GET is served by /listings/nearby."""

    permission_classes = [IsVerified]  # FR-2: must be verified to post

    def get_throttles(self):
        if self.request.method == "POST":
            self.throttle_scope = "create_listing"  # §9.10: 10/day/user
        return super().get_throttles()

    @extend_schema(request=ListingCreateSerializer, responses=ListingDetailSerializer)
    def post(self, request):
        ser = ListingCreateSerializer(data=request.data, context={"request": request})
        ser.is_valid(raise_exception=True)
        listing = ser.save()
        # Fan out nearby push (§11) — high/critical requests and all new offers.
        self._maybe_fan_out(listing)
        return Response(
            ListingDetailSerializer(listing, context={"include_exact": True}).data,
            status=status.HTTP_201_CREATED,
        )

    def _maybe_fan_out(self, listing):
        from apps.notifications.models import Notification
        from apps.notifications.services import notify

        if listing.type == Listing.Type.REQUEST and listing.urgency not in ("high", "critical"):
            return
        ntype = (
            Notification.Type.NEARBY_REQUEST
            if listing.type == Listing.Type.REQUEST
            else Notification.Type.NEARBY_OFFER
        )
        blocked = _blocked_user_ids(listing.author)
        from apps.identity.models import User

        # Production: a Celery job geo-filters device owners within the radius.
        # Here: notify recently-active verified neighbours (excluding self/blocked).
        recipients = (
            User.objects.filter(is_phone_verified=True, status="active")
            .exclude(id=listing.author_id)
            .exclude(id__in=blocked)
            .filter(devices__isnull=False)
            .distinct()[:50]
        )
        for r in recipients:
            notify(r, ntype, context={"title": listing.title},
                   data={"listing_id": str(listing.id), "listing_type": listing.type})


class ListingNearbyView(APIView):
    """GET /listings/nearby — primary discovery endpoint (§9.5).

    Powers both the Needs and Offers tabs via ``type``. Filtering uses
    ``ST_DWithin(location_fuzzed, point, radius)`` (GiST-indexed) ordered by
    ``ST_Distance``; the response emits a banded distance over the fuzzed point
    so the client can't pinpoint anyone (§13.1).
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        parameters=[
            OpenApiParameter("type", str, required=True, enum=["request", "offer"]),
            OpenApiParameter("lat", float, required=True),
            OpenApiParameter("lng", float, required=True),
            OpenApiParameter("radius_km", float, description="default 5, max 25"),
            OpenApiParameter("category", str, description="category key, repeatable"),
            OpenApiParameter("urgency", str, description="requests only"),
            OpenApiParameter("q", str, description="full-text over title/description"),
            OpenApiParameter("cursor", str),
        ],
        responses=ListingCardSerializer(many=True),
    )
    def get(self, request):
        from django.conf import settings

        p = request.query_params
        listing_type = p.get("type")
        if listing_type not in (Listing.Type.REQUEST, Listing.Type.OFFER):
            raise ApiError("VALIDATION_ERROR", "Query param 'type' must be request or offer.")
        try:
            lat, lng = float(p["lat"]), float(p["lng"])
        except (KeyError, ValueError):
            raise ApiError("VALIDATION_ERROR", "Valid 'lat' and 'lng' are required.")

        max_km = settings.NEARAID["MAX_RADIUS_KM"]
        try:
            radius_km = min(float(p.get("radius_km", settings.NEARAID["DEFAULT_RADIUS_KM"])), max_km)
        except ValueError:
            radius_km = settings.NEARAID["DEFAULT_RADIUS_KM"]

        ref = Point(lng, lat, srid=4326)
        qs = (
            Listing.objects.filter(type=listing_type, status=Listing.Status.OPEN, is_hidden=False)
            .filter(expires_at__gt=timezone.now())
            .exclude(author_id__in=_blocked_user_ids(request.user))
            # ST_DWithin over the GiST-indexed fuzzed point, ordered by ST_Distance.
            .filter(location_fuzzed__dwithin=(ref, D(km=radius_km)))
            .annotate(distance=Distance("location_fuzzed", ref))
            .order_by("distance")
            .select_related("category", "author")
            .prefetch_related("images")
        )
        categories = p.getlist("category")
        if categories:
            qs = qs.filter(category__key__in=categories)
        if listing_type == Listing.Type.REQUEST and p.get("urgency"):
            qs = qs.filter(urgency=p["urgency"])
        if p.get("q"):
            qs = qs.filter(Q(title__icontains=p["q"]) | Q(description__icontains=p["q"]))

        # Lightweight offset cursor (stable for a feed snapshot); paged in the DB.
        page_size = 20
        offset = self._decode_cursor(p.get("cursor"))
        window = list(qs[offset:offset + page_size + 1])
        has_more = len(window) > page_size
        window = window[:page_size]
        for obj in window:
            obj.distance_km = distance_band(obj.distance.km)
        next_cursor = self._encode_cursor(offset + page_size) if has_more else None

        return Response(
            {
                "results": ListingCardSerializer(window, many=True).data,
                "next_cursor": next_cursor,
                "has_more": has_more,
            }
        )

    @staticmethod
    def _encode_cursor(offset):
        return base64.urlsafe_b64encode(f"o={offset}".encode()).decode()

    @staticmethod
    def _decode_cursor(cursor):
        if not cursor:
            return 0
        try:
            raw = base64.urlsafe_b64decode(cursor.encode()).decode()
            return max(0, int(raw.split("=", 1)[1]))
        except Exception:
            return 0


class ListingDetailView(APIView):
    """GET/PATCH /listings/{id} and POST /listings/{id}/cancel (§9.5)."""

    permission_classes = [IsAuthenticated]

    def get_object(self, listing_id):
        return get_object_or_404(
            Listing.objects.select_related("category", "author").prefetch_related("images"),
            pk=listing_id,
        )

    def get(self, request, listing_id):
        listing = self.get_object(listing_id)
        # Exact location → owner or the active-claim counterpart only (§9.5, §13.1).
        claim = listing.active_claim
        include_exact = listing.author_id == request.user.id or (
            claim is not None and claim.claimant_id == request.user.id
        )
        return Response(
            ListingDetailSerializer(listing, context={"include_exact": include_exact}).data
        )

    @extend_schema(request=ListingEditSerializer, responses=ListingDetailSerializer)
    def patch(self, request, listing_id):
        listing = self.get_object(listing_id)
        if listing.author_id != request.user.id:
            raise ApiError("FORBIDDEN", "You can only edit your own listing.", status_code=403)
        if listing.status != Listing.Status.OPEN:
            raise ApiError("CONFLICT", "Only OPEN listings can be edited.", status_code=409)
        ser = ListingEditSerializer(listing, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(
            ListingDetailSerializer(listing, context={"include_exact": True}).data
        )


class ListingCancelView(APIView):
    """POST /listings/{id}/cancel — owner cancels while OPEN/CLAIMED (§9.5, §14)."""

    permission_classes = [IsAuthenticated]

    def post(self, request, listing_id):
        listing = get_object_or_404(Listing, pk=listing_id)
        if listing.author_id != request.user.id:
            raise ApiError("FORBIDDEN", "You can only cancel your own listing.", status_code=403)
        if listing.status not in (Listing.Status.OPEN, Listing.Status.CLAIMED):
            raise ApiError("CONFLICT", "This listing can no longer be cancelled.", status_code=409)
        # Late cancellation (after a claim) dents trust (§13.4).
        if listing.status == Listing.Status.CLAIMED:
            request.user.adjust_trust(-2)
            claim = listing.active_claim
            if claim:
                claim.status = "cancelled"
                claim.save(update_fields=["status"])
        listing.status = Listing.Status.CANCELLED
        listing.save(update_fields=["status", "updated_at"])
        return Response({"id": str(listing.id), "status": listing.status})


class MyListingsView(APIView):
    """GET /me/listings?type=&status= — the user's own posted listings (§9.5)."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = Listing.objects.filter(author=request.user).select_related("category", "author")
        if request.query_params.get("type"):
            qs = qs.filter(type=request.query_params["type"])
        if request.query_params.get("status"):
            qs = qs.filter(status=request.query_params["status"])
        from apps.common.pagination import CursorEnvelopePagination

        paginator = CursorEnvelopePagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        return paginator.get_paginated_response(ListingDetailSerializer(page, many=True).data)
