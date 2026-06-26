from rest_framework.permissions import BasePermission


class IsVerified(BasePermission):
    """OTP-verified account. FR-2: verification is mandatory before posting/claiming."""

    message = "Verify your phone number before posting or claiming."

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_phone_verified)


class IsActiveAccount(BasePermission):
    """Blocks suspended/banned accounts from acting (§12 user management)."""

    message = "Your account is not active."

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.status == "active")


class IsStaff(BasePermission):
    """Any admin-panel staff member — moderator or admin (§12.3)."""

    message = "Staff access required."

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.staff_role in ("moderator", "admin"))


class IsAdmin(BasePermission):
    """Admin-only staff actions: bans, category/config edits, audit log (§12.3)."""

    message = "Admin access required."

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.staff_role == "admin")
