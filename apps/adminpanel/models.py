import uuid

from django.conf import settings
from django.db import models


class PlatformConfig(models.Model):
    """Single-row platform configuration (§12 Configuration).

    Editable via PATCH /admin/v1/config; read everywhere through
    ``apps.common.conf.platform_conf``. Defaults mirror ``settings.NEARAID``.
    """

    request_ttl_days = models.PositiveSmallIntegerField(default=7)            # FR-9
    offer_default_window_hours = models.PositiveSmallIntegerField(default=24)  # FR-OF-4
    fuzz_radius_m = models.PositiveSmallIntegerField(default=400)             # §13.1
    auto_hide_reports = models.PositiveSmallIntegerField(default=3)           # FR-23
    max_listings_per_day = models.PositiveSmallIntegerField(default=10)       # §9.10
    max_claims_per_day = models.PositiveSmallIntegerField(default=30)
    notifications_enabled = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "platform configuration"

    def __str__(self):
        return "Platform configuration"

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def save(self, *args, **kwargs):
        self.pk = 1  # enforce single row
        super().save(*args, **kwargs)


class AuditLog(models.Model):
    """Immutable record of every staff action (§12 Audit log)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL,
                              related_name="audit_actions")
    action = models.CharField(max_length=60)
    target = models.CharField(max_length=120, help_text="e.g. user:<id>, listing:<id>")
    reason = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.action} → {self.target}"

    @classmethod
    def record(cls, actor, action, target, reason=""):
        return cls.objects.create(actor=actor, action=action, target=target, reason=reason)
