"""
Root URL configuration — the single API ingress (§6 / §9).

Public mobile API is mounted under ``/v1/...`` (base URL in the docs:
``https://api.nearaid.app/v1``). The web admin panel lives under ``/admin/v1/...``
(§12) and requires a staff JWT. Legacy ``/v1/requests/*`` paths alias
``type=request`` listings (§9.5).
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

from apps.common.views import health

V1 = "v1/"

urlpatterns = [
    path("django-admin/", admin.site.urls),
    path("health/", health, name="health"),
    # ── Public mobile API (§9) ──────────────────────────────────────────────
    path(f"{V1}auth/", include("apps.identity.urls_auth")),
    path(f"{V1}", include("apps.identity.urls_me")),          # /me, /users/{id}, /me/devices …
    path(f"{V1}", include("apps.listings.urls")),             # /categories, /listings …
    path(f"{V1}", include("apps.claims.urls")),               # /claims/{id}/…
    path(f"{V1}", include("apps.chat.urls")),                 # /me/conversations, /claims/{id}/messages
    path(f"{V1}", include("apps.ratings.urls")),              # /claims/{id}/rating, /users/{id}/ratings
    path(f"{V1}", include("apps.safety.urls")),               # /reports, /blocks
    path(f"{V1}", include("apps.notifications.urls")),         # /me/notifications
    # ── Admin panel API (§12) ───────────────────────────────────────────────
    path("admin/v1/", include("apps.adminpanel.urls")),
    # ── OpenAPI schema + docs ───────────────────────────────────────────────
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
