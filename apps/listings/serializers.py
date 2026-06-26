from rest_framework import serializers

from apps.identity.serializers import AuthorSerializer

from .models import Category, Listing, ListingImage


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ("id", "key", "name_en", "name_bn", "icon", "is_active")


class CategoryRefSerializer(serializers.ModelSerializer):
    """Compact category block embedded in listing responses."""

    class Meta:
        model = Category
        fields = ("id", "key", "name_en", "name_bn", "icon")


class ListingImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ListingImage
        fields = ("id", "url", "thumbnail_url")


class ListingCreateSerializer(serializers.Serializer):
    """POST /listings (§9.5). Requests take urgency; offers take available_until."""

    type = serializers.ChoiceField(choices=Listing.Type.choices)
    category_id = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.filter(is_active=True), source="category"
    )
    title = serializers.CharField(max_length=120)
    description = serializers.CharField(required=False, allow_blank=True, default="")
    quantity = serializers.CharField(max_length=60, required=False, allow_blank=True, default="")
    urgency = serializers.ChoiceField(choices=Listing.Urgency.choices, required=False, allow_null=True)
    available_until = serializers.DateTimeField(required=False, allow_null=True)
    lat = serializers.DecimalField(max_digits=9, decimal_places=6)
    lng = serializers.DecimalField(max_digits=9, decimal_places=6)
    area_label = serializers.CharField(max_length=120, required=False, allow_blank=True, default="")
    image_urls = serializers.ListField(
        child=serializers.URLField(), required=False, default=list,
        max_length=3,  # FR-5 / FR-OF-1: max 3 photos
    )

    def validate(self, attrs):
        if attrs["type"] == Listing.Type.REQUEST and not attrs.get("urgency"):
            raise serializers.ValidationError({"urgency": "Urgency is required for a request."})
        if attrs["type"] == Listing.Type.OFFER:
            attrs["urgency"] = None  # offers never carry urgency (FR-OF-2)
        return attrs

    def create(self, validated):
        image_urls = validated.pop("image_urls", [])
        listing = Listing.objects.create(author=self.context["request"].user, **validated)
        ListingImage.objects.bulk_create(
            [ListingImage(listing=listing, url=u) for u in image_urls]
        )
        return listing


class ListingEditSerializer(serializers.ModelSerializer):
    """PATCH /listings/{id} — owner only, OPEN only (§9.5)."""

    class Meta:
        model = Listing
        fields = ("title", "description", "quantity", "urgency", "available_until")


class ListingCardSerializer(serializers.ModelSerializer):
    """A discovery-feed card (§9.5 GET /listings/nearby). Fuzzed point + banded
    distance only — exact coordinates are never present here."""

    category = CategoryRefSerializer(read_only=True)
    author = AuthorSerializer(read_only=True)
    location_fuzzed = serializers.SerializerMethodField()
    distance_km = serializers.SerializerMethodField()
    thumbnail_url = serializers.SerializerMethodField()

    class Meta:
        model = Listing
        fields = (
            "id", "type", "title", "category", "urgency", "available_until",
            "quantity", "distance_km", "area_label", "location_fuzzed",
            "thumbnail_url", "author", "status", "created_at",
        )

    def get_location_fuzzed(self, obj):
        return {"lat": float(obj.lat_fuzzed), "lng": float(obj.lng_fuzzed)}

    def get_distance_km(self, obj):
        return getattr(obj, "distance_km", None)

    def get_thumbnail_url(self, obj):
        first = obj.images.first()
        return (first.thumbnail_url or first.url) if first else None


class ListingDetailSerializer(serializers.ModelSerializer):
    """GET /listings/{id} (§9.5). Exact location returned only to the owner or
    the active-claim counterpart — enforced in the view via ``include_exact``."""

    category = CategoryRefSerializer(read_only=True)
    author = AuthorSerializer(read_only=True)
    images = ListingImageSerializer(many=True, read_only=True)
    location_fuzzed = serializers.SerializerMethodField()
    location_exact = serializers.SerializerMethodField()

    class Meta:
        model = Listing
        fields = (
            "id", "type", "status", "title", "description", "quantity",
            "category", "urgency", "available_until", "area_label",
            "location_fuzzed", "location_exact", "images", "author",
            "expires_at", "created_at", "updated_at",
        )

    def get_location_fuzzed(self, obj):
        return {"lat": float(obj.lat_fuzzed), "lng": float(obj.lng_fuzzed)}

    def get_location_exact(self, obj):
        if self.context.get("include_exact"):
            return {"lat": float(obj.lat), "lng": float(obj.lng)}
        return None
