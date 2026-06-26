from rest_framework import serializers

from .models import ChatMessage


class ChatMessageSerializer(serializers.ModelSerializer):
    thread_id = serializers.SerializerMethodField()

    class Meta:
        model = ChatMessage
        fields = ("id", "thread_id", "claim", "sender", "type", "body", "image_url",
                  "read_at", "created_at")
        read_only_fields = ("id", "thread_id", "claim", "sender", "read_at", "created_at")

    def get_thread_id(self, obj):
        return ChatMessage.thread_id_for(obj.claim_id)


class SendMessageSerializer(serializers.Serializer):
    type = serializers.ChoiceField(choices=ChatMessage.Type.choices, default=ChatMessage.Type.TEXT)
    body = serializers.CharField(required=False, allow_blank=True, default="")
    image_url = serializers.URLField(required=False, allow_blank=True, default="")

    def validate(self, attrs):
        if attrs["type"] == ChatMessage.Type.TEXT and not attrs.get("body"):
            raise serializers.ValidationError({"body": "Text messages need a body."})
        if attrs["type"] == ChatMessage.Type.IMAGE and not attrs.get("image_url"):
            raise serializers.ValidationError({"image_url": "Image messages need an image_url."})
        return attrs


class ConversationSerializer(serializers.Serializer):
    """One row in the Messages tab (§9.7 GET /me/conversations)."""

    thread_id = serializers.CharField()
    claim_id = serializers.UUIDField()
    listing = serializers.DictField()
    counterpart = serializers.DictField()
    role = serializers.CharField()
    last_message = serializers.DictField(allow_null=True)
    unread_count = serializers.IntegerField()
    listing_status = serializers.CharField()
