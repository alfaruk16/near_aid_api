import uuid

from django.conf import settings
from django.db import models


class Report(models.Model):
    """Report a user or a listing (§8.2 reports, §9.9, FR-22/FR-23)."""

    class TargetType(models.TextChoices):
        USER = "user", "User"
        LISTING = "listing", "Listing"

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        REVIEWING = "reviewing", "Reviewing"
        RESOLVED = "resolved", "Resolved"
        DISMISSED = "dismissed", "Dismissed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reporter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                 related_name="reports_filed")
    target_type = models.CharField(max_length=8, choices=TargetType.choices)
    target_id = models.UUIDField(help_text="UUID of the reported user or listing")
    reason = models.CharField(max_length=255)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.OPEN)
    resolution_note = models.CharField(max_length=255, blank=True)
    resolved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                    on_delete=models.SET_NULL, related_name="reports_resolved")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [models.Index(fields=["target_type", "target_id", "status"])]

    def __str__(self):
        return f"report {self.id} on {self.target_type}:{self.target_id}"


class Block(models.Model):
    """User blocks another; they disappear from each other's feeds (§8.2 blocks, FR-22)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    blocker = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                related_name="blocks_made")
    blocked = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                related_name="blocks_against")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        constraints = [
            models.UniqueConstraint(fields=["blocker", "blocked"], name="uniq_block_pair")
        ]

    def __str__(self):
        return f"{self.blocker_id} ⊘ {self.blocked_id}"
