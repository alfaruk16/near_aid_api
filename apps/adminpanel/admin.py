from django.contrib import admin

from .models import AuditLog, PlatformConfig


@admin.register(PlatformConfig)
class PlatformConfigAdmin(admin.ModelAdmin):
    list_display = ("request_ttl_days", "offer_default_window_hours", "fuzz_radius_m",
                    "auto_hide_reports", "notifications_enabled", "updated_at")


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("action", "target", "actor", "created_at")
    list_filter = ("action",)
    search_fields = ("target", "reason")
    readonly_fields = ("id", "actor", "action", "target", "reason", "created_at")

    def has_change_permission(self, request, obj=None):
        return False  # immutable (§12)

    def has_delete_permission(self, request, obj=None):
        return False
