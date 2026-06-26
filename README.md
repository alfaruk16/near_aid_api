# NearAid API

Backend for **NearAid** — a hyperlocal mutual-aid platform connecting people who
need everyday aid (food, clothes, medicine, goods, shelter) with nearby people
willing to help. Requests ("I need X") and offers ("I have X to give") are two
types of a single **listing**, so they share discovery, chat, claims, ratings and
moderation. The platform connects people; the physical handoff happens offline.
Money is intentionally out of scope for v1.

This implements the **NearAid Technical Documentation v1.1** (`../near_aid_documents`).

## Architecture

A **modular monolith** (Django REST Framework) — each app under `apps/` maps to
one service box in §6 of the docs:

| App | Service box | Responsibility |
|-----|-------------|----------------|
| `common` | — | Shared base models, geo helpers, cursor pagination, error envelope, permissions |
| `identity` | Auth | Phone-OTP login (JWT), profile, ID verification, devices |
| `listings` | Listings / Geo | Categories, requests & offers, nearby discovery |
| `claims` | — | Claim → deliver → confirm lifecycle (server-enforced state machine) |
| `chat` | Chat (WebSocket) | 1:1 thread per claim, REST history + realtime (Channels) |
| `ratings` | — | Two-way ratings + trust score events (§13.4) |
| `safety` | — | Reports, blocks, auto-hide threshold |
| `notifications` | FCM fan-out | Device tokens + push triggers (§11) |
| `adminpanel` | Moderation / Admin | `/admin/v1` metrics, moderation, config, audit log (§12) |

The public mobile API is mounted under `/v1/...`; the web admin panel under
`/admin/v1/...` (staff JWT). Realtime chat is served over `/ws` by Django Channels.

## Quick start

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env                 # then set up PostGIS — see "Geospatial" below
python manage.py migrate
python manage.py seed_demo           # categories, staff, neighbours, listings
python manage.py runserver
```

Then open:

* **Swagger UI** — http://127.0.0.1:8000/api/docs/
* **ReDoc** — http://127.0.0.1:8000/api/redoc/
* **OpenAPI schema** — http://127.0.0.1:8000/api/schema/

### Demo accounts (after `seed_demo`)

| Account | Phone | Notes |
|---------|-------|-------|
| Admin | `+8801700000000` | `staff_role=admin`; Django-admin pw `admin12345` |
| Moderator | `+8801700000001` | `staff_role=moderator` |
| Neighbours | `+88017100000{01..05}` | Nadia, Faruk, Shahana, Rakib, Mim (Dhaka) |

All accounts log in via OTP. In `DEBUG`, `POST /v1/auth/otp/request` returns the
code in `debug_code`, and the fixed code **`123456`** always verifies (set
`OTP_DEBUG_CODE=""` to disable).

### Try the flow

```bash
# 1. Request + verify OTP → tokens
curl -X POST localhost:8000/v1/auth/otp/request -d '{"phone":"+8801710000002"}' -H 'Content-Type: application/json'
curl -X POST localhost:8000/v1/auth/otp/verify  -d '{"request_id":"<id>","code":"123456"}' -H 'Content-Type: application/json'

# 2. Discover nearby offers (banded distance, fuzzed point — never exact)
curl 'localhost:8000/v1/listings/nearby?type=offer&lat=23.7461&lng=90.3742&radius_km=25' \
     -H 'Authorization: Bearer <access_token>'

# 3. Claim → message → deliver → confirm → rate
curl -X POST localhost:8000/v1/listings/<id>/claim   -H 'Authorization: Bearer <helper>'
curl -X POST localhost:8000/v1/claims/<id>/deliver   -H 'Authorization: Bearer <helper>'
curl -X POST localhost:8000/v1/claims/<id>/confirm   -H 'Authorization: Bearer <seeker>'
curl -X POST localhost:8000/v1/claims/<id>/rating    -H 'Authorization: Bearer <seeker>' \
     -d '{"score":5,"comment":"Kind and on time."}' -H 'Content-Type: application/json'
```

## API conventions (§9.1)

* **Auth** — `Authorization: Bearer <access_token>` (JWT) on everything except the
  OTP endpoints. Refresh at `POST /v1/auth/refresh`.
* **Errors** — consistent envelope:
  `{"error": {"code": "ALREADY_CLAIMED", "message": "...", "details": {...}}}`.
* **Pagination** — cursor: `{"results": [...], "next_cursor": "...", "has_more": true}`.
* **Rate limits** (§9.10) — OTP 5/hr, create-listing 10/day, claim 30/day,
  messages 60/min, reports 20/day.

## Listing lifecycle (§14)

```
create ─► OPEN ──claim──► CLAIMED ──deliver──► DELIVERED ──confirm──► COMPLETED (ratings unlock)
                  │                                  
                  └─ withdraw ─► OPEN          OPEN/CLAIMED ─cancel─► CANCELLED
                                              OPEN ─TTL/window elapsed─► EXPIRED
```

The same machine governs requests and offers; only party labels differ. For a
**request** the claimant is the **Helper** and the owner (**Seeker**) confirms;
for an **offer** the claimant is the **Recipient** and the owner (**Giver**)
confirms. The fulfilling party always marks *deliver*; the receiving party always
*confirms*. Invalid transitions return `409`.

## Privacy (§13.1)

Exact coordinates are **never** returned by public endpoints — only a
server-jittered point (±300–500 m) and a banded distance. The exact point is
revealed only to the listing owner and the active-claim counterpart (so they can
meet), and would be encrypted at rest in production.

## Geospatial

Discovery runs on **PostgreSQL + PostGIS** via GeoDjango. A listing stores two
`geography(Point, 4326)` columns — `location` (exact, never exposed) and
`location_fuzzed` (jittered ±300–500 m, GiST-indexed). `GET /listings/nearby`
filters with `ST_DWithin(location_fuzzed, point, radius)` and orders by
`ST_Distance`, then emits a *banded* distance so the client never gets a pin
(§13.1). Point fuzzing and distance banding live in `apps/common/geo.py`.

**Local setup (macOS / Homebrew):**

```bash
brew install geos proj gdal postgis postgresql@17   # postgis needs pg@17/@18
brew services start postgresql@17
createuser -s nearaid 2>/dev/null; createdb -O nearaid nearaid
psql -d nearaid -c 'CREATE EXTENSION IF NOT EXISTS postgis;'
```

Connection settings come from `.env` (`DB_NAME`/`DB_USER`/`DB_PASSWORD`, default
`nearaid`). Because Django 4.2 only auto-probes GDAL ≤ 3.6, `config/settings.py`
points `GDAL_LIBRARY_PATH` / `GEOS_LIBRARY_PATH` at the Homebrew dylibs (override
via the same-named env vars on other platforms).

PostGIS is required — the spatial models can't migrate on plain SQLite.

## Realtime chat (§10)

Connect to `ws://127.0.0.1:8000/ws?token=<access_token>` (served by Channels via
ASGI). Client events: `subscribe`, `message.send`, `typing`, `message.read`.
Server events: `message.new`, `message.read`, `typing`. A thread maps 1:1 to a
claim and subscription is authorized by claim membership. With `REDIS_URL` set,
the Channels layer uses Redis; otherwise an in-memory layer (single process).

Run with an ASGI server for WebSocket support:

```bash
pip install uvicorn   # or daphne
uvicorn config.asgi:application
```

## Configuration

Runtime tunables (request TTL, offer window, fuzz radius, auto-hide threshold,
rate limits) live in a single `PlatformConfig` row, editable by admins via
`PATCH /admin/v1/config` and read everywhere through `apps.common.conf`. Defaults
come from `settings.NEARAID` / `.env`. Every staff mutation is written to the
immutable audit log.

## Notifications

`apps/notifications/services.notify()` persists a localized notification and logs
the FCM payload a Celery worker would send. In production, swap `_push_to_devices`
for the real FCM client and move fan-out into Celery tasks (§11, §22).
# near_aid_api
