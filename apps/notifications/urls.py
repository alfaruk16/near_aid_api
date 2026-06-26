from django.urls import path

from .views import NotificationListView, NotificationReadAllView

urlpatterns = [
    path("me/notifications", NotificationListView.as_view(), name="me-notifications"),
    path("me/notifications/read", NotificationReadAllView.as_view(), name="me-notifications-read"),
]
