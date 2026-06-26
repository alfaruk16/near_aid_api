from django.contrib import admin

from .models import OTPCode, User, Verification


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("phone", "display_name", "staff_role", "status", "is_phone_verified",
                    "is_id_verified", "trust_score", "created_at")
    list_filter = ("status", "staff_role", "is_phone_verified", "is_id_verified", "language")
    search_fields = ("phone", "display_name", "email")
    readonly_fields = ("id", "created_at", "updated_at", "last_login")


@admin.register(Verification)
class VerificationAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "status", "reviewer", "created_at", "reviewed_at")
    list_filter = ("status",)
    search_fields = ("user__phone", "user__display_name")
    raw_id_fields = ("user", "reviewer")


@admin.register(OTPCode)
class OTPCodeAdmin(admin.ModelAdmin):
    list_display = ("request_id", "phone", "purpose", "consumed", "attempts", "expires_at")
    list_filter = ("purpose", "consumed")
    search_fields = ("phone", "request_id")
