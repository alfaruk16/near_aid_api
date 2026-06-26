from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.conf import platform_conf
from apps.common.exceptions import ApiError
from apps.common.pagination import CursorEnvelopePagination
from apps.identity.models import User

from .models import Block, Report
from .serializers import BlockSerializer, ReportCreateSerializer


class ReportCreateView(APIView):
    """POST /reports — report a user or listing (§9.9, FR-22)."""

    permission_classes = [IsAuthenticated]
    throttle_scope = "reports"  # §9.10: 20/day/user

    def post(self, request):
        ser = ReportCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        report = Report.objects.create(reporter=request.user, **ser.validated_data)
        self._maybe_auto_hide(report)
        return Response({"id": str(report.id), "status": report.status},
                        status=status.HTTP_201_CREATED)

    def _maybe_auto_hide(self, report):
        """FR-23: auto-hide content after N open reports, pending moderator review."""
        if report.target_type != Report.TargetType.LISTING:
            return
        threshold = platform_conf().auto_hide_reports
        open_count = Report.objects.filter(
            target_type=Report.TargetType.LISTING,
            target_id=report.target_id,
            status=Report.Status.OPEN,
        ).count()
        if open_count >= threshold:
            from apps.listings.models import Listing

            Listing.objects.filter(pk=report.target_id, is_hidden=False).update(is_hidden=True)


class BlockView(APIView):
    """POST /blocks and DELETE /blocks/{user_id} — block / unblock (§9.9)."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        blocked_id = request.data.get("user_id")
        if not blocked_id:
            raise ApiError("VALIDATION_ERROR", "user_id is required.")
        if str(blocked_id) == str(request.user.id):
            raise ApiError("INVALID", "You cannot block yourself.")
        blocked = get_object_or_404(User, pk=blocked_id)
        block, _ = Block.objects.get_or_create(blocker=request.user, blocked=blocked)
        return Response(BlockSerializer(block).data, status=status.HTTP_201_CREATED)

    def delete(self, request, user_id):
        Block.objects.filter(blocker=request.user, blocked_id=user_id).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class MyBlocksView(APIView):
    """GET /me/blocks — list blocked users (§9.9)."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = Block.objects.filter(blocker=request.user).select_related("blocked")
        paginator = CursorEnvelopePagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        return paginator.get_paginated_response(BlockSerializer(page, many=True).data)
