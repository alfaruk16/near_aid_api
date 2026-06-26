import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q


class Claim(models.Model):
    """A claim on a listing (§8.2 claims, §9.6, §14).

    The claimant is the Helper (claiming a request) or the Recipient (claiming
    an offer). A listing holds at most one *active* claim at a time, enforced by
    a partial unique index.
    """

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        WITHDRAWN = "withdrawn", "Withdrawn"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    listing = models.ForeignKey("listings.Listing", on_delete=models.CASCADE, related_name="claims")
    claimant = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                 related_name="claims")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)

    claimed_at = models.DateTimeField(auto_now_add=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-claimed_at",)
        constraints = [
            # §8.2: one active claim per listing.
            models.UniqueConstraint(
                fields=["listing"],
                condition=Q(status="active"),
                name="uniq_active_claim_per_listing",
            )
        ]

    def __str__(self):
        return f"claim {self.id} on {self.listing_id} ({self.status})"

    # Party roles depend on the listing type (§14). The fulfilling party marks
    # DELIVERED; the receiving party CONFIRMS.
    @property
    def fulfilling_user_id(self):
        """Helper for a request; Giver (listing owner) for an offer."""
        if self.listing.type == "request":
            return self.claimant_id
        return self.listing.author_id

    @property
    def receiving_user_id(self):
        """Seeker (listing owner) for a request; Recipient (claimant) for an offer."""
        if self.listing.type == "request":
            return self.listing.author_id
        return self.claimant_id

    @property
    def counterpart_of(self):
        """Return a callable mapping a user id → the other party's id."""
        def other(user_id):
            return self.listing.author_id if user_id == self.claimant_id else self.claimant_id
        return other
