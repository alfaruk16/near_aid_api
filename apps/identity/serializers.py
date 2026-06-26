from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken

from apps.notifications.models import Device

from .models import User, Verification


def tokens_for(user):
    refresh = RefreshToken.for_user(user)
    return {"access_token": str(refresh.access_token), "refresh_token": str(refresh)}


class MeSerializer(serializers.ModelSerializer):
    """Full profile of the authenticated user (§9.3 GET /me)."""

    class Meta:
        model = User
        fields = (
            "id", "phone", "email", "display_name", "photo_url", "language",
            "default_area", "is_phone_verified", "is_id_verified", "trust_score",
            "status", "created_at",
        )
        read_only_fields = (
            "id", "phone", "is_phone_verified", "is_id_verified", "trust_score",
            "status", "created_at",
        )


class PublicUserSerializer(serializers.ModelSerializer):
    """Public profile (§9.3 GET /users/{id}). No phone, no location."""

    rating_avg = serializers.SerializerMethodField()
    rating_count = serializers.SerializerMethodField()
    completed_count = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id", "display_name", "photo_url", "trust_score", "is_id_verified",
            "rating_avg", "rating_count", "completed_count", "created_at",
        )

    def get_rating_avg(self, obj):
        from django.db.models import Avg

        agg = obj.ratings_received.aggregate(v=Avg("score"))["v"]
        return round(agg, 2) if agg is not None else None

    def get_rating_count(self, obj):
        return obj.ratings_received.count()

    def get_completed_count(self, obj):
        # Completed exchanges this user took part in (as claimant or listing owner).
        from apps.claims.models import Claim

        return Claim.objects.filter(claimant=obj, status=Claim.Status.COMPLETED).count()


class AuthorSerializer(serializers.ModelSerializer):
    """Compact author/counterpart block embedded in listings, claims, chat."""

    class Meta:
        model = User
        fields = ("id", "display_name", "photo_url", "trust_score", "is_id_verified")


# ── Auth flow (§9.2) ───────────────────────────────────────────────────────────
class OTPRequestSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=20)

    def validate_phone(self, value):
        digits = "".join(ch for ch in value if ch.isdigit())
        if len(digits) < 10:
            raise serializers.ValidationError("Enter a valid mobile number.")
        return value.strip()


class OTPVerifySerializer(serializers.Serializer):
    request_id = serializers.CharField(max_length=24)
    code = serializers.CharField(max_length=6)


# ── Devices (§9.3 POST /me/devices) ─────────────────────────────────────────────
class DeviceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Device
        fields = ("id", "fcm_token", "platform", "last_seen")
        read_only_fields = ("id", "last_seen")


# ── Verification (§9.3 POST /me/verification) ───────────────────────────────────
class VerificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Verification
        fields = ("id", "document", "status", "reason", "created_at", "reviewed_at")
        read_only_fields = ("id", "status", "reason", "created_at", "reviewed_at")
