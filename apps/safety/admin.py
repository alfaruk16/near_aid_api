from django.contrib import admin

from .models import Block, Report


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ("id", "target_type", "target_id", "reporter", "status", "created_at")
    list_filter = ("target_type", "status")
    search_fields = ("reason", "reporter__phone")
    raw_id_fields = ("reporter", "resolved_by")


@admin.register(Block)
class BlockAdmin(admin.ModelAdmin):
    list_display = ("blocker", "blocked", "created_at")
    search_fields = ("blocker__phone", "blocked__phone")
    raw_id_fields = ("blocker", "blocked")
