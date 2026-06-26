"""
Realtime chat consumer (§10).

Client → Server events: ``subscribe``, ``message.send``, ``typing``,
``message.read`` (keyed by ``thread_id``).
Server → Client events: ``message.new``, ``message.read``, ``typing``,
``claim.updated``, ``listing.claimed``.

A thread maps 1:1 to a claim; the channel group is ``thread_<claim_uuid_hex>``.
Subscription is authorized by claim membership.
"""
import uuid

from asgiref.sync import sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer


class ChatConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        user = self.scope.get("user")
        if not user or not user.is_authenticated:
            await self.close(code=4401)  # unauthenticated
            return
        self.user = user
        self.groups_joined = set()
        await self.accept()

    async def disconnect(self, code):
        for group in getattr(self, "groups_joined", set()):
            await self.channel_layer.group_discard(group, self.channel_name)

    async def receive_json(self, content, **kwargs):
        event = content.get("event")
        if event == "subscribe":
            await self._subscribe(content.get("thread_id"))
        elif event == "message.send":
            await self._send_message(content)
        elif event == "typing":
            await self._relay_typing(content)
        elif event == "message.read":
            await self._relay_read(content)

    # ── helpers ──────────────────────────────────────────────────────────────
    async def _claim_for_thread(self, thread_id):
        """thread_id is 'thr_<first 12 hex of claim uuid>'. Resolve + authorize."""
        if not thread_id or not thread_id.startswith("thr_"):
            return None
        prefix = thread_id[4:]
        return await sync_to_async(self._lookup_claim)(prefix)

    def _lookup_claim(self, prefix):
        from apps.claims.models import Claim

        for claim in Claim.objects.select_related("listing").all():
            if claim.id.hex[:12] == prefix:
                if self.user.id in (claim.claimant_id, claim.listing.author_id):
                    return claim
                return None
        return None

    async def _subscribe(self, thread_id):
        claim = await self._claim_for_thread(thread_id)
        if not claim:
            await self.send_json({"event": "error", "message": "Cannot subscribe to this thread."})
            return
        group = f"thread_{claim.id.hex}"
        await self.channel_layer.group_add(group, self.channel_name)
        self.groups_joined.add(group)
        await self.send_json({"event": "subscribed", "thread_id": thread_id})

    async def _send_message(self, content):
        claim = await self._claim_for_thread(content.get("thread_id"))
        if not claim:
            return
        msg = await sync_to_async(self._persist)(claim, content)
        group = f"thread_{claim.id.hex}"
        await self.channel_layer.group_send(
            group,
            {"type": "chat.message", "payload": {"event": "message.new",
             "thread_id": content["thread_id"], "message": msg}},
        )

    def _persist(self, claim, content):
        from .models import ChatMessage
        from .serializers import ChatMessageSerializer

        msg = ChatMessage.objects.create(
            claim=claim, sender=self.user,
            type=content.get("type", "text"),
            body=content.get("body", ""),
            image_url=content.get("image_url", ""),
        )
        return ChatMessageSerializer(msg).data

    async def _relay_typing(self, content):
        claim = await self._claim_for_thread(content.get("thread_id"))
        if not claim:
            return
        await self.channel_layer.group_send(
            f"thread_{claim.id.hex}",
            {"type": "chat.event", "payload": {"event": "typing",
             "thread_id": content["thread_id"], "user_id": str(self.user.id),
             "is_typing": bool(content.get("is_typing"))}},
        )

    async def _relay_read(self, content):
        claim = await self._claim_for_thread(content.get("thread_id"))
        if not claim:
            return
        await sync_to_async(self._mark_read)(claim)
        await self.channel_layer.group_send(
            f"thread_{claim.id.hex}",
            {"type": "chat.event", "payload": {"event": "message.read",
             "thread_id": content["thread_id"], "reader_id": str(self.user.id),
             "up_to": content.get("up_to")}},
        )

    def _mark_read(self, claim):
        from django.utils import timezone

        claim.messages.filter(read_at__isnull=True).exclude(sender=self.user).update(
            read_at=timezone.now()
        )

    # ── group event handlers ───────────────────────────────────────────────────
    async def chat_message(self, event):
        await self.send_json(event["payload"])

    async def chat_event(self, event):
        await self.send_json(event["payload"])
