import uuid
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.common.conf import platform_conf
from apps.common.geo import fuzz_point


class Category(models.Model):
    """Shared by requests and offers (§8.2 categories, FR-6). No money category."""

    key = models.SlugField(max_length=20, unique=True)
    name_en = models.CharField(max_length=40)
    name_bn = models.CharField(max_length=40)
    icon = models.CharField(max_length=40, blank=True)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ("sort_order", "id")
        verbose_name_plural = "categories"

    def __str__(self):
        return self.name_en


class Listing(models.Model):
    """Unifies requests and offers (§8.2 listings). A ``type`` discriminator is
    the only structural difference; discovery, claims, chat, ratings and
    moderation all reuse this one table."""

    class Type(models.TextChoices):
        REQUEST = "request", "Request (I need)"
        OFFER = "offer", "Offer (I have)"

    class Urgency(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"
        CRITICAL = "critical", "Critical"

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        CLAIMED = "claimed", "Claimed"
        DELIVERED = "delivered", "Delivered"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"
        EXPIRED = "expired", "Expired"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    type = models.CharField(max_length=8, choices=Type.choices)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                               related_name="listings")
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="listings")

    title = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    quantity = models.CharField(max_length=60, blank=True, help_text='e.g. "3 meals", "winter, M"')

    # Requests carry urgency (FR-5); offers carry an availability window (FR-OF-1).
    urgency = models.CharField(max_length=8, choices=Urgency.choices, null=True, blank=True)
    available_until = models.DateTimeField(null=True, blank=True)

    status = models.CharField(max_length=10, choices=Status.choices, default=Status.OPEN, db_index=True)

    # §13.1 location privacy: the exact point is stored (never exposed publicly,
    # encrypted at rest in production) and a jittered point is what discovery uses.
    lat = models.DecimalField(max_digits=9, decimal_places=6)
    lng = models.DecimalField(max_digits=9, decimal_places=6)
    lat_fuzzed = models.DecimalField(max_digits=9, decimal_places=6)
    lng_fuzzed = models.DecimalField(max_digits=9, decimal_places=6)
    area_label = models.CharField(max_length=120, blank=True, help_text='e.g. "Mirpur, Dhaka"')

    expires_at = models.DateTimeField(db_index=True)
    # FR-23: auto-hidden after N reports, pending moderation. Excluded from discovery.
    is_hidden = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            # §8.2 discovery index — equivalent of idx_listings_type_status.
            models.Index(fields=["type", "status"]),
            models.Index(fields=["expires_at"]),
        ]

    def __str__(self):
        return f"[{self.type}] {self.title}"

    def save(self, *args, **kwargs):
        conf = platform_conf()
        if self.lat is not None and self.lng is not None and self.lat_fuzzed is None:
            self.lat_fuzzed, self.lng_fuzzed = fuzz_point(self.lat, self.lng, conf.fuzz_radius_m)
        if not self.expires_at:
            self.expires_at = self._default_expiry(conf)
        super().save(*args, **kwargs)

    def _default_expiry(self, conf):
        """Requests expire after the TTL; offers at their window (or TTL, sooner) — §14."""
        ttl = timezone.now() + timedelta(days=conf.request_ttl_days)
        if self.type == self.Type.OFFER:
            window = self.available_until or (
                timezone.now() + timedelta(hours=conf.offer_default_window_hours)
            )
            return min(window, ttl)
        return ttl

    @property
    def is_expired(self):
        return self.status == self.Status.OPEN and timezone.now() >= self.expires_at

    @property
    def active_claim(self):
        return self.claims.filter(status="active").first()


class ListingImage(models.Model):
    """Up to 3 photos per listing (FR-5 / FR-OF-1)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name="images")
    url = models.URLField()
    thumbnail_url = models.URLField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("created_at",)

    def __str__(self):
        return self.url
