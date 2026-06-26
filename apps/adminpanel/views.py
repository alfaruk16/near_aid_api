"""
Admin panel API (§12). All endpoints under /admin/v1 require a staff JWT;
admin-only actions (bans, category/config edits, audit log) additionally
require ``staff_role == admin`` (§12.3). Every staff mutation is recorded in the
immutable AuditLog.
"""
from django.db.models import Avg, Count, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.claims.models import Claim
from apps.common.exceptions import ApiError
from apps.common.pagination import CursorEnvelopePagination
from apps.common.permissions import IsAdmin, IsStaff
from apps.identity.models import User, Verification
from apps.listings.models import Category, Listing
from apps.notifications.models import Notification
from apps.notifications.services import notify
from apps.safety.models import Report

from .models import AuditLog, PlatformConfig
from .serializers import (
    AdminCategorySerializer,
    AdminListingSerializer,
    AdminReportSerializer,
    AdminVerificationSerializer,
    AuditLogSerializer,
    PlatformConfigSerializer,
    StaffUserSerializer,
)


def _paginate(view, qs, serializer_cls, request, ordering="-created_at"):
    paginator = CursorEnvelopePagination()
    paginator.ordering = ordering
    page = paginator.paginate_queryset(qs, request, view=view)
    return paginator.get_paginated_response(serializer_cls(page, many=True).data)


# ── Dashboard (§12.1) ───────────────────────────────────────────────────────────
class MetricsOverviewView(APIView):
    permission_classes = [IsStaff]

    def get(self, request):
        listings = Listing.objects.all()
        completed = Claim.objects.filter(status=Claim.Status.COMPLETED).count()
        total_claims = Claim.objects.count()
        by_category = list(
            listings.values("category__key").annotate(count=Count("id")).order_by("-count")
        )
        return Response(
            {
                "users": {
                    "total": User.objects.filter(staff_role="none").count(),
                    "verified": User.objects.filter(is_id_verified=True).count(),
                    "suspended": User.objects.filter(status="suspended").count(),
                    "banned": User.objects.filter(status="banned").count(),
                },
                "listings": {
                    "open_requests": listings.filter(type="request", status="open").count(),
                    "open_offers": listings.filter(type="offer", status="open").count(),
                    "completed": listings.filter(status="completed").count(),
                },
                "completion_rate": round(completed / total_claims, 3) if total_claims else 0,
                "open_reports": Report.objects.filter(status="open").count(),
                "pending_verifications": Verification.objects.filter(status="pending").count(),
                "listings_by_category": by_category,
            }
        )


# ── User management (§12.1) ─────────────────────────────────────────────────────
class AdminUserListView(APIView):
    permission_classes = [IsStaff]

    def get(self, request):
        qs = User.objects.all()
        p = request.query_params
        if p.get("status"):
            qs = qs.filter(status=p["status"])
        if p.get("q"):
            qs = qs.filter(Q(phone__icontains=p["q"]) | Q(display_name__icontains=p["q"]))
        if p.get("min_trust"):
            qs = qs.filter(trust_score__gte=p["min_trust"])
        return _paginate(self, qs, StaffUserSerializer, request)


class AdminUserDetailView(APIView):
    permission_classes = [IsStaff]

    def get(self, request, user_id):
        user = get_object_or_404(User, pk=user_id)
        data = StaffUserSerializer(user).data
        data["listings_count"] = user.listings.count()
        data["claims_count"] = user.claims.count()
        data["ratings_received"] = user.ratings_received.count()
        data["reports_against"] = Report.objects.filter(
            target_type="user", target_id=user.id
        ).count()
        return Response(data)


class _UserStatusAction(APIView):
    permission_classes = [IsAdmin]
    target_status = None
    action_name = ""

    def post(self, request, user_id):
        user = get_object_or_404(User, pk=user_id)
        user.status = self.target_status
        user.save(update_fields=["status", "updated_at"])
        AuditLog.record(request.user, self.action_name, f"user:{user.id}",
                        request.data.get("reason", ""))
        notify(user, Notification.Type.MODERATION,
               context={"title": f"Your account was {self.target_status}."})
        return Response(StaffUserSerializer(user).data)


class AdminUserSuspendView(_UserStatusAction):
    target_status = User.Status.SUSPENDED
    action_name = "user.suspend"


class AdminUserBanView(_UserStatusAction):
    target_status = User.Status.BANNED
    action_name = "user.ban"


class AdminUserUnbanView(_UserStatusAction):
    target_status = User.Status.ACTIVE
    action_name = "user.unban"


# ── Verification queue (§12.1) ───────────────────────────────────────────────────
class AdminVerificationListView(APIView):
    permission_classes = [IsStaff]

    def get(self, request):
        qs = Verification.objects.select_related("user")
        qs = qs.filter(status=request.query_params.get("status", "pending"))
        return _paginate(self, qs, AdminVerificationSerializer, request)


class AdminVerificationApproveView(APIView):
    permission_classes = [IsStaff]

    def post(self, request, verification_id):
        ver = get_object_or_404(Verification, pk=verification_id)
        ver.status = Verification.Status.APPROVED
        ver.reviewer = request.user
        ver.reviewed_at = timezone.now()
        ver.save(update_fields=["status", "reviewer", "reviewed_at"])
        # §13.4: +5 trust on ID verification.
        ver.user.is_id_verified = True
        ver.user.save(update_fields=["is_id_verified", "updated_at"])
        ver.user.adjust_trust(5)
        AuditLog.record(request.user, "verification.approve", f"user:{ver.user_id}")
        notify(ver.user, Notification.Type.MODERATION,
               context={"title": "Your ID was verified — you now have the Verified badge."})
        return Response(AdminVerificationSerializer(ver).data)


class AdminVerificationRejectView(APIView):
    permission_classes = [IsStaff]

    def post(self, request, verification_id):
        ver = get_object_or_404(Verification, pk=verification_id)
        ver.status = Verification.Status.REJECTED
        ver.reviewer = request.user
        ver.reviewed_at = timezone.now()
        ver.reason = request.data.get("reason", "")
        ver.save(update_fields=["status", "reviewer", "reviewed_at", "reason"])
        AuditLog.record(request.user, "verification.reject", f"user:{ver.user_id}", ver.reason)
        return Response(AdminVerificationSerializer(ver).data)


# ── Listing moderation (§12.1) ───────────────────────────────────────────────────
class AdminListingListView(APIView):
    permission_classes = [IsStaff]

    def get(self, request):
        qs = Listing.objects.select_related("author", "category")
        p = request.query_params
        if p.get("type"):
            qs = qs.filter(type=p["type"])
        if p.get("status"):
            qs = qs.filter(status=p["status"])
        if p.get("category"):
            qs = qs.filter(category__key=p["category"])
        if p.get("flagged") == "true":
            qs = qs.filter(is_hidden=True)
        return _paginate(self, qs, AdminListingSerializer, request)


class AdminListingTakedownView(APIView):
    permission_classes = [IsStaff]

    def post(self, request, listing_id):
        listing = get_object_or_404(Listing, pk=listing_id)
        listing.status = Listing.Status.CANCELLED
        listing.is_hidden = True
        listing.save(update_fields=["status", "is_hidden", "updated_at"])
        AuditLog.record(request.user, "listing.takedown", f"listing:{listing.id}",
                        request.data.get("reason", ""))
        notify(listing.author, Notification.Type.MODERATION,
               context={"title": "Your listing was removed by a moderator."})
        return Response(AdminListingSerializer(listing).data)


class AdminListingRestoreView(APIView):
    permission_classes = [IsStaff]

    def post(self, request, listing_id):
        listing = get_object_or_404(Listing, pk=listing_id)
        listing.is_hidden = False
        if listing.status == Listing.Status.CANCELLED:
            listing.status = Listing.Status.OPEN
        listing.save(update_fields=["status", "is_hidden", "updated_at"])
        AuditLog.record(request.user, "listing.restore", f"listing:{listing.id}")
        return Response(AdminListingSerializer(listing).data)


# ── Report queue (§12.1) ─────────────────────────────────────────────────────────
class AdminReportListView(APIView):
    permission_classes = [IsStaff]

    def get(self, request):
        qs = Report.objects.select_related("reporter")
        qs = qs.filter(status=request.query_params.get("status", "open"))
        return _paginate(self, qs, AdminReportSerializer, request)


class AdminReportResolveView(APIView):
    permission_classes = [IsStaff]

    def post(self, request, report_id):
        report = get_object_or_404(Report, pk=report_id)
        action = request.data.get("action", "")
        note = request.data.get("note", "")
        report.status = Report.Status.RESOLVED
        report.resolution_note = f"{action}: {note}".strip(": ")
        report.resolved_by = request.user
        report.save(update_fields=["status", "resolution_note", "resolved_by"])

        # Optional escalation actions.
        if action == "ban_user" and report.target_type == "user":
            User.objects.filter(pk=report.target_id).update(status="banned")
            # §13.4: −10 to a user with an upheld report.
            target = User.objects.filter(pk=report.target_id).first()
            if target:
                target.adjust_trust(-10)
        elif action == "takedown_listing" and report.target_type == "listing":
            Listing.objects.filter(pk=report.target_id).update(
                status="cancelled", is_hidden=True
            )
        AuditLog.record(request.user, "report.resolve",
                        f"{report.target_type}:{report.target_id}", report.resolution_note)
        return Response(AdminReportSerializer(report).data)


class AdminReportDismissView(APIView):
    permission_classes = [IsStaff]

    def post(self, request, report_id):
        report = get_object_or_404(Report, pk=report_id)
        report.status = Report.Status.DISMISSED
        report.resolved_by = request.user
        report.save(update_fields=["status", "resolved_by"])
        # Un-hide a listing whose reports were all dismissed.
        if report.target_type == "listing":
            still_open = Report.objects.filter(
                target_type="listing", target_id=report.target_id, status="open"
            ).exists()
            if not still_open:
                Listing.objects.filter(pk=report.target_id).update(is_hidden=False)
        AuditLog.record(request.user, "report.dismiss",
                        f"{report.target_type}:{report.target_id}")
        return Response(AdminReportSerializer(report).data)


# ── Category management (§12.1) ──────────────────────────────────────────────────
class AdminCategoryListCreateView(APIView):
    def get_permissions(self):
        return [IsAdmin()] if self.request.method == "POST" else [IsStaff()]

    def get(self, request):
        return Response({"results": AdminCategorySerializer(
            Category.objects.all(), many=True).data})

    def post(self, request):
        if request.data.get("key") == "money":
            raise ApiError("FORBIDDEN", "A money category cannot be created in v1.", status_code=403)
        ser = AdminCategorySerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        cat = ser.save()
        AuditLog.record(request.user, "category.create", f"category:{cat.id}")
        return Response(ser.data, status=status.HTTP_201_CREATED)


class AdminCategoryDetailView(APIView):
    permission_classes = [IsAdmin]

    def patch(self, request, category_id):
        cat = get_object_or_404(Category, pk=category_id)
        ser = AdminCategorySerializer(cat, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        AuditLog.record(request.user, "category.update", f"category:{cat.id}")
        return Response(ser.data)


# ── Configuration (§12.1) ────────────────────────────────────────────────────────
class AdminConfigView(APIView):
    def get_permissions(self):
        return [IsAdmin()] if self.request.method == "PATCH" else [IsStaff()]

    def get(self, request):
        return Response(PlatformConfigSerializer(PlatformConfig.load()).data)

    def patch(self, request):
        conf = PlatformConfig.load()
        ser = PlatformConfigSerializer(conf, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        AuditLog.record(request.user, "config.update", "platform:config",
                        ", ".join(request.data.keys()))
        return Response(ser.data)


# ── Audit log (§12.1) ────────────────────────────────────────────────────────────
class AdminAuditLogView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request):
        return _paginate(self, AuditLog.objects.select_related("actor"),
                         AuditLogSerializer, request)
