import random
import uuid
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone


class UserManager(BaseUserManager):
    def _create(self, phone, password, **extra):
        if not phone:
            raise ValueError("Phone number is required")
        phone = phone.strip()
        user = self.model(phone=phone, **extra)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_user(self, phone, password=None, **extra):
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._create(phone, password, **extra)

    def create_superuser(self, phone, password=None, **extra):
        extra.update(
            is_staff=True,
            is_superuser=True,
            is_active=True,
            staff_role=User.StaffRole.ADMIN,
            is_phone_verified=True,
        )
        return self._create(phone, password, **extra)


class User(AbstractBaseUser, PermissionsMixin):
    """Phone-first account (§8.2 users).

    A single verified account is a *dual user* (§3): role is contextual to each
    listing, not fixed on the account. ``staff_role`` is the orthogonal axis for
    admin-panel access (moderator/admin); end users have ``staff_role=none``.
    """

    class Language(models.TextChoices):
        BN = "bn", "বাংলা"
        EN = "en", "English"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        SUSPENDED = "suspended", "Suspended"
        BANNED = "banned", "Banned"

    class StaffRole(models.TextChoices):
        NONE = "none", "End user"
        MODERATOR = "moderator", "Moderator"
        ADMIN = "admin", "Admin"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    phone = models.CharField(max_length=20, unique=True, help_text="E.164, primary identity")
    email = models.EmailField(blank=True)
    display_name = models.CharField(max_length=80, blank=True)
    photo_url = models.URLField(blank=True)
    language = models.CharField(max_length=2, choices=Language.choices, default=Language.BN)
    default_area = models.CharField(max_length=120, blank=True, help_text="FR-3 default area label")

    is_phone_verified = models.BooleanField(default=False)
    is_id_verified = models.BooleanField(default=False, help_text='"Verified" badge — FR-4')
    trust_score = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("50.00"),
                                       help_text="0–100, computed (§13.4)")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)

    # Admin-panel access axis (§12.3). Independent of the mobile-app role.
    staff_role = models.CharField(max_length=10, choices=StaffRole.choices, default=StaffRole.NONE)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)  # Django-admin gate; staff_role drives the API
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = "phone"
    REQUIRED_FIELDS = []

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.display_name or self.phone}"

    # ── Trust score (§13.4) ──────────────────────────────────────────────────
    # Start at 50. Drives feed ranking and notification eligibility.
    def adjust_trust(self, delta):
        new = Decimal(self.trust_score) + Decimal(str(delta))
        self.trust_score = max(Decimal("0"), min(Decimal("100"), new))
        self.save(update_fields=["trust_score", "updated_at"])
        return self.trust_score


class OTPCode(models.Model):
    """One-time codes for phone verification / passwordless login (§9.2)."""

    class Purpose(models.TextChoices):
        LOGIN = "login", "Login / Register"
        VERIFY = "verify", "Verify phone"

    request_id = models.CharField(max_length=24, unique=True, default="", db_index=True)
    phone = models.CharField(max_length=20, db_index=True)
    code = models.CharField(max_length=6)
    purpose = models.CharField(max_length=10, choices=Purpose.choices, default=Purpose.LOGIN)
    expires_at = models.DateTimeField()
    consumed = models.BooleanField(default=False)
    attempts = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

    def is_valid(self):
        return not self.consumed and timezone.now() < self.expires_at and self.attempts < 5

    @classmethod
    def issue(cls, phone, purpose=Purpose.LOGIN, fixed_code=None, ttl_seconds=120):
        code = fixed_code or f"{random.randint(0, 999999):06d}"
        return cls.objects.create(
            request_id="otp_" + uuid.uuid4().hex[:12],
            phone=phone,
            code=code,
            purpose=purpose,
            expires_at=timezone.now() + timedelta(seconds=ttl_seconds),
        )


class Verification(models.Model):
    """ID verification submission for the Verified badge (FR-4, §9.3, §12)."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending review"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="verifications")
    document = models.FileField(upload_to="verifications/")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    reviewer = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL,
                                 related_name="reviewed_verifications")
    reason = models.CharField(max_length=255, blank=True, help_text="Rejection reason")
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"verification {self.id} ({self.status})"
