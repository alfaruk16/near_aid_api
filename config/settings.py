"""
Django settings for the NearAid API.

A **modular monolith** (Django REST Framework), per §6 of the technical
documentation: each Django app under ``apps/`` maps to one service box —
identity (Auth), listings (Listings/Geo), claims, chat (realtime), ratings,
safety, notifications (FCM fan-out), adminpanel (Moderation/Admin). A single
API surface (``config.urls``) is the ingress under ``/v1/...``.

The Listings/Geo service runs on PostgreSQL + PostGIS: ``location`` and
``location_fuzzed`` are ``geography(Point, 4326)`` columns (GiST-indexed) and
nearby discovery uses ``ST_DWithin`` / ``ST_Distance`` via GeoDjango. The
spatial models require PostGIS; connection settings come from ``.env`` (see
README → "Geospatial").
"""
from datetime import timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


# ── Minimal .env loader (no hard dependency on python-dotenv) ───────────────────
def _load_env():
    """Load KEY=VALUE pairs from the nearest .env into os.environ (no overwrite)."""
    import os

    for candidate in (BASE_DIR / ".env", BASE_DIR.parent / ".env"):
        if not candidate.exists():
            continue
        for raw in candidate.read_text().splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())
        break


_load_env()

import os  # noqa: E402


def env(key, default=None):
    return os.environ.get(key, default)


def env_bool(key, default=False):
    return str(env(key, default)).lower() in ("1", "true", "yes", "on")


def env_int(key, default=0):
    try:
        return int(env(key, default))
    except (TypeError, ValueError):
        return default


def env_list(key, default=""):
    raw = env(key, default) or ""
    return [item.strip() for item in raw.split(",") if item.strip()]


# ── Core ───────────────────────────────────────────────────────────────────────
SECRET_KEY = env("SECRET_KEY", "dev-insecure-change-me")
DEBUG = env_bool("DEBUG", True)
ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", "*") or ["*"]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.gis",
    # Third party
    "rest_framework",
    "rest_framework_simplejwt",
    "django_filters",
    "corsheaders",
    "drf_spectacular",
    "channels",
    # Local apps (one per service box in §6)
    "apps.common",
    "apps.identity",
    "apps.listings",
    "apps.claims",
    "apps.chat",
    "apps.ratings",
    "apps.safety",
    "apps.notifications",
    "apps.adminpanel",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"


# ── Data layer ── PostgreSQL + PostGIS (required; see README → "Geospatial"). ───
DATABASES = {
    "default": {
        "ENGINE": "django.contrib.gis.db.backends.postgis",
        "NAME": env("DB_NAME", "nearaid"),
        "USER": env("DB_USER", "nearaid"),
        "PASSWORD": env("DB_PASSWORD", "nearaid"),
        "HOST": env("DB_HOST", "127.0.0.1"),
        "PORT": env("DB_PORT", "5432"),
    }
}

# GeoDjango needs the GEOS/GDAL shared libraries. Django 4.2's auto-discovery
# only probes GDAL ≤ 3.6, so newer Homebrew GDAL (3.13) must be pointed at
# explicitly. Honour an env override, else fall back to the Homebrew paths when
# present; left unset elsewhere so non-spatial setups don't require GDAL.
import os.path as _osp  # noqa: E402

_geos = env("GEOS_LIBRARY_PATH", "/opt/homebrew/opt/geos/lib/libgeos_c.dylib")
_gdal = env("GDAL_LIBRARY_PATH", "/opt/homebrew/opt/gdal/lib/libgdal.dylib")
if _osp.exists(_geos):
    GEOS_LIBRARY_PATH = _geos
if _osp.exists(_gdal):
    GDAL_LIBRARY_PATH = _gdal


# ── Cache + Channels layer ── Redis (optional; in-memory fallback) ──────────────
REDIS_URL = env("REDIS_URL")
if REDIS_URL:
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.redis.RedisCache", "LOCATION": REDIS_URL}}
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {"hosts": [REDIS_URL]},
        }
    }
else:
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
    CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}


AUTH_USER_MODEL = "identity.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Dhaka"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "static"
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# ── DRF ──────────────────────────────────────────────────────────────────────
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    # §9.1 — cursor pagination with the {results, next_cursor, has_more} envelope.
    "DEFAULT_PAGINATION_CLASS": "apps.common.pagination.CursorEnvelopePagination",
    "PAGE_SIZE": 20,
    "DEFAULT_FILTER_BACKENDS": (
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ),
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    # §9.1 — consistent error envelope {"error": {code, message, details}}.
    "EXCEPTION_HANDLER": "apps.common.exceptions.envelope_exception_handler",
    "DEFAULT_THROTTLE_CLASSES": ("rest_framework.throttling.ScopedRateThrottle",),
    # §9.10 — suggested rate limits.
    "DEFAULT_THROTTLE_RATES": {
        "otp": "5/hour",
        "create_listing": "10/day",
        "claim": "30/day",
        "messages": "60/min",
        "reports": "20/day",
    },
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=12),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=30),
    "AUTH_HEADER_TYPES": ("Bearer",),
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "NearAid API",
    "DESCRIPTION": "Hyperlocal mutual-aid platform. Two-sided board of requests "
    "and offers unified as one listing concept, with claim/fulfil workflow, "
    "in-app chat, ratings, trust score, safety, and an admin moderation panel. "
    "Modular monolith per the NearAid Technical Documentation v1.1.",
    "VERSION": "1.1.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
}

CORS_ALLOWED_ORIGINS = env_list("CORS_ALLOWED_ORIGINS")
CORS_ALLOW_ALL_ORIGINS = DEBUG and not CORS_ALLOWED_ORIGINS


# ── NearAid platform configuration (admin-tunable; see §12 Configuration) ───────
# These are the runtime defaults; the live values are stored in a single
# PlatformConfig row (apps.adminpanel) and editable via PATCH /admin/v1/config.
NEARAID = {
    "REQUEST_TTL_DAYS": env_int("REQUEST_TTL_DAYS", 7),       # FR-9
    "OFFER_DEFAULT_WINDOW_HOURS": env_int("OFFER_WINDOW_HOURS", 24),  # FR-OF-4
    "FUZZ_RADIUS_M": env_int("FUZZ_RADIUS_M", 400),           # §13.1 ±300–500 m
    "DEFAULT_RADIUS_KM": 5,                                    # §9.5
    "MAX_RADIUS_KM": 25,
    "MAX_IMAGES": 3,                                           # FR-5 / FR-OF-1
    "AUTO_HIDE_REPORTS": env_int("AUTO_HIDE_REPORTS", 3),      # FR-23
}

# Demo OTP code (the UI mockup hints "use 123456"). Set OTP_DEBUG_CODE="" to disable.
OTP_DEBUG_CODE = env("OTP_DEBUG_CODE", "123456")
