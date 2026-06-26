from django.urls import path

from .consumers import ChatConsumer

# §10 — wss://api.nearaid.app/ws?token=<access_token>
websocket_urlpatterns = [
    path("ws", ChatConsumer.as_asgi()),
]
