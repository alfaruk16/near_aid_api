"""Admin panel API (§12.2). Mounted at /admin/v1/."""
from django.urls import path

from .views import (
    AdminAuditLogView,
    AdminCategoryDetailView,
    AdminCategoryListCreateView,
    AdminConfigView,
    AdminListingListView,
    AdminListingRestoreView,
    AdminListingTakedownView,
    AdminReportDismissView,
    AdminReportListView,
    AdminReportResolveView,
    AdminUserBanView,
    AdminUserDetailView,
    AdminUserListView,
    AdminUserSuspendView,
    AdminUserUnbanView,
    AdminVerificationApproveView,
    AdminVerificationListView,
    AdminVerificationRejectView,
    MetricsOverviewView,
)

urlpatterns = [
    path("metrics/overview", MetricsOverviewView.as_view(), name="admin-metrics"),
    # Users
    path("users", AdminUserListView.as_view(), name="admin-users"),
    path("users/<uuid:user_id>", AdminUserDetailView.as_view(), name="admin-user-detail"),
    path("users/<uuid:user_id>/suspend", AdminUserSuspendView.as_view(), name="admin-user-suspend"),
    path("users/<uuid:user_id>/ban", AdminUserBanView.as_view(), name="admin-user-ban"),
    path("users/<uuid:user_id>/unban", AdminUserUnbanView.as_view(), name="admin-user-unban"),
    # Verifications
    path("verifications", AdminVerificationListView.as_view(), name="admin-verifications"),
    path("verifications/<uuid:verification_id>/approve", AdminVerificationApproveView.as_view(),
         name="admin-verification-approve"),
    path("verifications/<uuid:verification_id>/reject", AdminVerificationRejectView.as_view(),
         name="admin-verification-reject"),
    # Listings
    path("listings", AdminListingListView.as_view(), name="admin-listings"),
    path("listings/<uuid:listing_id>/takedown", AdminListingTakedownView.as_view(),
         name="admin-listing-takedown"),
    path("listings/<uuid:listing_id>/restore", AdminListingRestoreView.as_view(),
         name="admin-listing-restore"),
    # Reports
    path("reports", AdminReportListView.as_view(), name="admin-reports"),
    path("reports/<uuid:report_id>/resolve", AdminReportResolveView.as_view(),
         name="admin-report-resolve"),
    path("reports/<uuid:report_id>/dismiss", AdminReportDismissView.as_view(),
         name="admin-report-dismiss"),
    # Categories
    path("categories", AdminCategoryListCreateView.as_view(), name="admin-categories"),
    path("categories/<int:category_id>", AdminCategoryDetailView.as_view(),
         name="admin-category-detail"),
    # Config + audit
    path("config", AdminConfigView.as_view(), name="admin-config"),
    path("audit-log", AdminAuditLogView.as_view(), name="admin-audit-log"),
]
