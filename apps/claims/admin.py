from django.contrib import admin

from .models import Claim


@admin.register(Claim)
class ClaimAdmin(admin.ModelAdmin):
    list_display = ("id", "listing", "claimant", "status", "claimed_at", "delivered_at", "completed_at")
    list_filter = ("status",)
    search_fields = ("listing__title", "claimant__phone")
    raw_id_fields = ("listing", "claimant")
