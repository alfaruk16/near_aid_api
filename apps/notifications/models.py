import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class Device(models.Model):
    """FCM token registration (§8.2 devices, §11 push)."""

    class Platform(models.TextChoices):
        ANDROID = "android", "Android"
        IOS = "ios", "iOS"
        WEB = "web", "Web"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="devices")
    fcm_token = models.CharField(max_length=255, unique=True)
    platform = models.CharField(max_length=10, choices=Platform.choices, default=Platform.ANDROID)
    last_seen = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ("-last_seen",)

    def __str__(self):
        return f"{self.user_id} · {self.platform}"


class Notification(models.Model):
    """A push notification record (§11). In production an FCM message is sent;
    here it is persisted so the client can also fetch a history."""

    class Type(models.TextChoices):
        NEARBY_REQUEST = "nearby_request", "Nearby request"
        NEARBY_OFFER = "nearby_offer", "Nearby offer"
        REQUEST_CLAIMED = "request_claimed", "Request claimed"
        OFFER_REQUESTED = "offer_requested", "Offer requested"
        CHAT_MESSAGE = "chat_message", "Chat message"
        CLAIM_DELIVERED = "claim_delivered", "Marked delivered"
        CLAIM_COMPLETED = "claim_completed", "Receipt confirmed"
        NEW_RATING = "new_rating", "New rating"
        MODERATION = "moderation", "Moderation action"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                  related_name="notifications")
    type = models.CharField(max_length=20, choices=Type.choices)
    title = models.CharField(max_length=120)
    body = models.CharField(max_length=255)
    data = models.JSONField(default=dict, blank=True, help_text="deeplink + ids (§11)")
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.type} → {self.recipient_id}"
