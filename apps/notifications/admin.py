from django.contrib import admin

from .models import Device, Notification


@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = ("user", "platform", "last_seen")
    list_filter = ("platform",)
    search_fields = ("user__phone", "fcm_token")
    raw_id_fields = ("user",)


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("type", "recipient", "title", "read_at", "created_at")
    list_filter = ("type",)
    search_fields = ("recipient__phone", "title")
    raw_id_fields = ("recipient",)
