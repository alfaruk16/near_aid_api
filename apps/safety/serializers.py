from rest_framework import serializers

from apps.identity.serializers import AuthorSerializer

from .models import Block, Report


class ReportCreateSerializer(serializers.Serializer):
    target_type = serializers.ChoiceField(choices=Report.TargetType.choices)
    target_id = serializers.UUIDField()
    reason = serializers.CharField(max_length=255)


class BlockSerializer(serializers.ModelSerializer):
    blocked = AuthorSerializer(read_only=True)

    class Meta:
        model = Block
        fields = ("id", "blocked", "created_at")
