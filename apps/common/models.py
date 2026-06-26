import uuid

from django.db import models


class TimeStampedModel(models.Model):
    """Abstract base giving every row created/updated timestamps."""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        ordering = ("-created_at",)


class UUIDModel(TimeStampedModel):
    """Timestamped base with a UUID primary key.

    The data model (§8) uses UUID PKs for users, listings, claims, and the
    other user-facing rows so IDs are unguessable and safe to expose.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True
        ordering = ("-created_at",)
