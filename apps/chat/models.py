import uuid

from django.conf import settings
from django.db import models


class ChatMessage(models.Model):
    """A message in a claim's 1:1 thread (§8.2 chat_messages, §9.7).

    There is exactly one thread per claim, so ``claim`` is the thread key.
    Phone numbers are masked; coordination stays in-app (FR-18).
    """

    class Type(models.TextChoices):
        TEXT = "text", "Text"
        IMAGE = "image", "Image"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    claim = models.ForeignKey("claims.Claim", on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                               related_name="sent_messages")
    type = models.CharField(max_length=6, choices=Type.choices, default=Type.TEXT)
    body = models.TextField(blank=True)
    image_url = models.URLField(blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("created_at",)
        indexes = [models.Index(fields=["claim", "created_at"])]

    def __str__(self):
        return f"msg {self.id} in claim {self.claim_id}"

    @staticmethod
    def thread_id_for(claim_id):
        return f"thr_{claim_id.hex[:12]}" if hasattr(claim_id, "hex") else f"thr_{claim_id}"
