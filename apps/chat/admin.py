from django.contrib import admin

from .models import ChatMessage


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ("id", "claim", "sender", "type", "read_at", "created_at")
    list_filter = ("type",)
    search_fields = ("body", "sender__phone")
    raw_id_fields = ("claim", "sender")
