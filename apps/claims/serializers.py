from rest_framework import serializers

from apps.identity.serializers import AuthorSerializer

from .models import Claim


class ClaimSerializer(serializers.ModelSerializer):
    listing_type = serializers.CharField(source="listing.type", read_only=True)
    listing_id = serializers.UUIDField(source="listing.id", read_only=True)
    chat_thread_id = serializers.SerializerMethodField()

    class Meta:
        model = Claim
        fields = (
            "id", "listing_id", "listing_type", "status", "chat_thread_id",
            "claimed_at", "delivered_at", "completed_at",
        )

    def get_chat_thread_id(self, obj):
        # One thread per claim; the claim id is the thread id (§9.7/§10).
        return f"thr_{obj.id.hex[:12]}"


class MyClaimSerializer(serializers.ModelSerializer):
    """GET /me/claims — a claim with listing + counterpart context (§9.6)."""

    listing = serializers.SerializerMethodField()
    counterpart = serializers.SerializerMethodField()
    role = serializers.SerializerMethodField()

    class Meta:
        model = Claim
        fields = ("id", "status", "listing", "counterpart", "role",
                  "claimed_at", "delivered_at", "completed_at")

    def get_listing(self, obj):
        l = obj.listing
        return {"id": str(l.id), "type": l.type, "title": l.title, "status": l.status}

    def get_counterpart(self, obj):
        return AuthorSerializer(obj.listing.author).data

    def get_role(self, obj):
        # The claimant helps a request, or receives an offer.
        return "helping" if obj.listing.type == "request" else "receiving"
