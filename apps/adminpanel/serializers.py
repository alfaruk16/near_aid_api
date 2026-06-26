from rest_framework import serializers

from apps.identity.models import User, Verification
from apps.listings.models import Category, Listing
from apps.safety.models import Report

from .models import AuditLog, PlatformConfig


class StaffUserSerializer(serializers.ModelSerializer):
    """User row for the admin user-management module (§12)."""

    class Meta:
        model = User
        fields = ("id", "phone", "display_name", "email", "status", "staff_role",
                  "is_phone_verified", "is_id_verified", "trust_score", "created_at")


class AdminListingSerializer(serializers.ModelSerializer):
    author = StaffUserSerializer(read_only=True)
    category_key = serializers.CharField(source="category.key", read_only=True)
    # Staff see the exact area (§12 listing moderation).
    location_exact = serializers.SerializerMethodField()

    class Meta:
        model = Listing
        fields = ("id", "type", "status", "title", "description", "category_key",
                  "urgency", "area_label", "location_exact", "is_hidden", "author",
                  "expires_at", "created_at")

    def get_location_exact(self, obj):
        return {"lat": float(obj.lat), "lng": float(obj.lng)}


class AdminVerificationSerializer(serializers.ModelSerializer):
    user = StaffUserSerializer(read_only=True)

    class Meta:
        model = Verification
        fields = ("id", "user", "document", "status", "reason", "created_at", "reviewed_at")


class AdminReportSerializer(serializers.ModelSerializer):
    reporter = StaffUserSerializer(read_only=True)

    class Meta:
        model = Report
        fields = ("id", "target_type", "target_id", "reason", "status",
                  "resolution_note", "reporter", "created_at")


class AdminCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ("id", "key", "name_en", "name_bn", "icon", "is_active", "sort_order")


class PlatformConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlatformConfig
        exclude = ("id",)


class AuditLogSerializer(serializers.ModelSerializer):
    actor = serializers.SerializerMethodField()

    class Meta:
        model = AuditLog
        fields = ("id", "actor", "action", "target", "reason", "created_at")

    def get_actor(self, obj):
        return {"id": str(obj.actor_id), "name": obj.actor.display_name or obj.actor.phone} if obj.actor else None
