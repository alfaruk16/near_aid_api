"""Chat & conversations (§9.7). Mounted at /v1/."""
from django.urls import path

from .views import ConversationListView, MessageListCreateView, MessageReadView

urlpatterns = [
    path("me/conversations", ConversationListView.as_view(), name="me-conversations"),
    path("claims/<uuid:claim_id>/messages", MessageListCreateView.as_view(), name="claim-messages"),
    path("claims/<uuid:claim_id>/messages/read", MessageReadView.as_view(), name="claim-messages-read"),
]
