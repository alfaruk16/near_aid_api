"""Safety — reports & blocks (§9.9). Mounted at /v1/."""
from django.urls import path

from .views import BlockView, MyBlocksView, ReportCreateView

urlpatterns = [
    path("reports", ReportCreateView.as_view(), name="reports"),
    path("blocks", BlockView.as_view(), name="blocks"),
    path("blocks/<uuid:user_id>", BlockView.as_view(), name="block-delete"),
    path("me/blocks", MyBlocksView.as_view(), name="me-blocks"),
]
