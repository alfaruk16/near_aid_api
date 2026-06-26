from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.exceptions import ApiError
from apps.common.pagination import CursorEnvelopePagination
from apps.claims.models import Claim
from apps.identity.serializers import AuthorSerializer
from apps.notifications.models import Notification
from apps.notifications.services import notify

from .models import ChatMessage
from .serializers import (
    ChatMessageSerializer,
    ConversationSerializer,
    SendMessageSerializer,
)

# FR-19: suggested safe public meetup points surfaced in the chat header.
SAFE_MEETUP_POINTS = [
    {"name": "Mirpur 10 Police Box", "area": "Mirpur, Dhaka"},
    {"name": "Dhanmondi 27 Community Centre", "area": "Dhanmondi, Dhaka"},
    {"name": "Gulshan 2 Circle (public forecourt)", "area": "Gulshan, Dhaka"},
]


def _membership(claim, user):
    """Both parties of a claim may access its thread; nobody else."""
    return user.id in (claim.claimant_id, claim.listing.author_id)


def _counterpart_id(claim, user):
    return claim.listing.author_id if user.id == claim.claimant_id else claim.claimant_id


class ConversationListView(APIView):
    """GET /me/conversations — the Messages tab (§9.7, FR-MSG-1)."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        claims = (
            Claim.objects.filter(Q(claimant=user) | Q(listing__author=user))
            .exclude(status=Claim.Status.WITHDRAWN)
            .select_related("listing", "listing__author", "claimant")
            .order_by("-claimed_at")
        )
        rows = []
        for claim in claims:
            counterpart = claim.listing.author if user.id == claim.claimant_id else claim.claimant
            last = claim.messages.order_by("-created_at").first()
            unread = claim.messages.filter(read_at__isnull=True).exclude(sender=user).count()
            rows.append(
                {
                    "thread_id": ChatMessage.thread_id_for(claim.id),
                    "claim_id": claim.id,
                    "listing": {
                        "id": str(claim.listing.id),
                        "type": claim.listing.type,
                        "title": claim.listing.title,
                    },
                    "counterpart": AuthorSerializer(counterpart).data,
                    "role": "helping" if (user.id == claim.claimant_id and claim.listing.type == "request")
                            else "receiving" if user.id == claim.claimant_id else "owner",
                    "last_message": (
                        {"body": last.body or "[image]", "created_at": last.created_at}
                        if last else None
                    ),
                    "unread_count": unread,
                    "listing_status": claim.listing.status,
                }
            )
        return Response({"results": ConversationSerializer(rows, many=True).data,
                         "next_cursor": None, "has_more": False})


class MessageListCreateView(APIView):
    """GET/POST /claims/{id}/messages — thread history + send (§9.7)."""

    permission_classes = [IsAuthenticated]

    def get_throttles(self):
        if self.request.method == "POST":
            self.throttle_scope = "messages"  # §9.10: 60/min/user
        return super().get_throttles()

    def get_claim(self, claim_id):
        claim = get_object_or_404(
            Claim.objects.select_related("listing", "listing__author", "claimant"), pk=claim_id
        )
        if not _membership(claim, self.request.user):
            raise ApiError("FORBIDDEN", "You are not part of this conversation.", status_code=403)
        return claim

    def get(self, request, claim_id):
        claim = self.get_claim(claim_id)
        qs = claim.messages.select_related("sender")
        paginator = CursorEnvelopePagination()
        paginator.ordering = "created_at"
        page = paginator.paginate_queryset(qs, request, view=self)
        resp = paginator.get_paginated_response(ChatMessageSerializer(page, many=True).data)
        resp.data["safe_meetup_points"] = SAFE_MEETUP_POINTS  # FR-19 chat header
        return resp

    def post(self, request, claim_id):
        claim = self.get_claim(claim_id)
        ser = SendMessageSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        msg = ChatMessage.objects.create(
            claim=claim, sender=request.user,
            type=ser.validated_data["type"],
            body=ser.validated_data.get("body", ""),
            image_url=ser.validated_data.get("image_url", ""),
        )
        data = ChatMessageSerializer(msg).data
        self._broadcast(claim, data)
        self._notify_recipient(claim, request.user, msg)
        return Response(data, status=status.HTTP_201_CREATED)

    def _broadcast(self, claim, data):
        layer = get_channel_layer()
        if not layer:
            return
        async_to_sync(layer.group_send)(
            f"thread_{claim.id.hex}",
            {"type": "chat.message", "payload": {"event": "message.new",
             "thread_id": ChatMessage.thread_id_for(claim.id), "message": data}},
        )

    def _notify_recipient(self, claim, sender, msg):
        from apps.identity.models import User

        recipient_id = _counterpart_id(claim, sender)
        recipient = User.objects.get(pk=recipient_id)
        notify(recipient, Notification.Type.CHAT_MESSAGE,
               context={"title": msg.body[:60] or "New image"},
               data={"claim_id": str(claim.id), "thread_id": ChatMessage.thread_id_for(claim.id)})


class MessageReadView(APIView):
    """POST /claims/{id}/messages/read — mark thread read (§9.7)."""

    permission_classes = [IsAuthenticated]

    def post(self, request, claim_id):
        claim = get_object_or_404(Claim.objects.select_related("listing"), pk=claim_id)
        if not _membership(claim, request.user):
            raise ApiError("FORBIDDEN", "You are not part of this conversation.", status_code=403)
        claim.messages.filter(read_at__isnull=True).exclude(sender=request.user).update(
            read_at=timezone.now()
        )
        return Response(status=status.HTTP_204_NO_CONTENT)
