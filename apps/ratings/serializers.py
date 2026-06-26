from rest_framework import serializers

from apps.identity.serializers import AuthorSerializer

from .models import Rating


class RatingCreateSerializer(serializers.Serializer):
    score = serializers.IntegerField(min_value=1, max_value=5)
    comment = serializers.CharField(required=False, allow_blank=True, default="")


class RatingSerializer(serializers.ModelSerializer):
    rater = AuthorSerializer(read_only=True)

    class Meta:
        model = Rating
        fields = ("id", "score", "comment", "rater", "created_at")
