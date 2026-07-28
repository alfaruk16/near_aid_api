# NearAid API — Resume Evidence Report

> Repo-grounded audit for a master resume. Every metric below is either backed by
> a file/command in this repo or explicitly marked **not evidenced**. Nothing is
> inferred.
>
> **Generated:** 2026-07-22 · **Repo:** `near_aid_api` · **Branch:** `main`

---

## ⚠️ Read this first

The original question template was written for an **Android / Kotlin Gradle
multi-module** project (Gradle version catalog, DI container, JaCoCo coverage,
macrobenchmark modules, CODEOWNERS). **This repo is none of those.** It is a
**Django (Python) REST API backend**. The Android-specific asks are therefore
structurally *not evidenced* here; the rest is reframed to what the repo actually
is.

**This project was vibe-coded (AI-generated in bulk), not hand-written
incrementally.** Represent it as an AI-assisted / vibe-coded prototype, not as
production engineering authored line-by-line. See [§7](#7-resume-honesty-notes).

---

## 1. Module structure

Not a Gradle multi-module project — no `settings.gradle`, no version catalog, no
submodules. It is a **single-package Django "modular monolith"**: one project,
**9 Django apps** under `apps/`, each mapping to one service box (`common` is
shared infrastructure).

| App | Responsibility | ~LOC (py) |
|-----|----------------|-----------|
| `identity` | Phone-OTP login (JWT), profile, ID verification, devices | 563 |
| `listings` | Categories, requests & offers, geo `/nearby` discovery | 688 |
| `claims` | Claim → deliver → confirm state machine (server-enforced) | 358 |
| `chat` | 1:1 thread per claim — REST history + realtime WebSocket | 515 |
| `ratings` | Two-way ratings + trust score | 180 |
| `safety` | Reports, blocks, auto-hide threshold | 239 |
| `notifications` | Device tokens + FCM push fan-out (stubbed) | 270 |
| `adminpanel` | `/admin/v1` metrics, moderation, config, audit log | 626 |
| `common` | Base models, geo helpers, cursor pagination, error envelope, permissions, seeders | 559 |

**Total ≈ 4,000 lines of Python** across the apps. Single Django project in
`config/` (settings, root urls, asgi/wsgi entrypoints).

---

## 2. Full stack

Source: `requirements.txt` + `config/settings.py`.

| Concern | Technology (evidenced) |
|---------|------------------------|
| Language / framework | Python 3.9+, Django 4.2 LTS, Django REST Framework 3.15 |
| Auth | SimpleJWT 5.3 (phone-OTP → JWT), PyJWT |
| Database / geo | PostgreSQL + **PostGIS** via GeoDjango (`django.contrib.gis`), psycopg2 — `geography(Point,4326)` columns, GiST index, `ST_DWithin` / `ST_Distance`. **No SQLite fallback** (spatial models require PostGIS) |
| Async / realtime | Django **Channels 4** over ASGI (WebSocket chat); `channels_redis` when `REDIS_URL` is set, in-memory channel layer otherwise |
| API tooling | drf-spectacular (OpenAPI + Swagger/ReDoc), django-filter, django-cors-headers |
| Media | Pillow |
| Dependency injection | N/A — Django uses no DI container. **Not evidenced / not applicable** |
| Testing | **Not evidenced** (see [§5](#5-hard-evidence-for-metrics)) |
| CI | **Not evidenced** — no `.github/`, no CI config of any kind |

---

## 3. What the app does / what shipped

**NearAid** — a hyperlocal mutual-aid API connecting people who need everyday aid
(food, clothes, medicine, shelter) with nearby people offering it. Requests and
offers are two faces of a single "listing" that share discovery, chat, claims,
ratings, and moderation. Money is intentionally out of scope for v1.

**Shipped (present in code):**

- OTP / JWT auth flow
- Geo discovery with privacy-preserving point fuzzing (±300–500 m) and banded distance
- Full claim lifecycle state machine (`OPEN → CLAIMED → DELIVERED → COMPLETED`, with withdraw / cancel / expire; invalid transitions return `409`)
- WebSocket chat with claim-membership authorization
- Two-way ratings + trust score
- Safety: reports / blocks / auto-hide threshold
- Admin panel: metrics, moderation, audit log
- Runtime-tunable `PlatformConfig` (admin-editable)
- OpenAPI docs (Swagger / ReDoc)
- Two idempotent seed commands (`seed_demo`, `seed_dummy`)

**Stubbed, NOT shipped:**

- FCM push — logs the payload a Celery worker *would* send
- Celery fan-out — explicitly "swap in production" per README

---

## 4. Attribution (git)

```
git log --author="alfarukemail@gmail.com" --oneline | wc -l   →  6
git rev-list --all --count                                    →  6
git shortlog -sne                                             →  6  faruk <alfarukemail@gmail.com>
```

**Sole contributor — 100% of commits are yours.**

Honest caveat: 5 of 6 commits are one-shot bulk drops, not incremental feature
work. The initial commit landed **all 9 apps at once** (~4k LOC in a single
"first commit"). The rest: "database upgraded to postGis", "dummy data added",
"updated readme", "otp limit in debug". There is no per-feature commit history to
attribute features to individuals — because there are no other individuals.

**Honest framing:** solo project, all commits yours, developed over ~2 days
(2026-06-26 → 2026-06-27). Not a team codebase where you owned a slice.

| Commit | Date | Message |
|--------|------|---------|
| 1 | 2026-06-26 | first commit |
| 2 | 2026-06-26 | first commit |
| 3 | 2026-06-27 | database upgraded to postGis |
| 4 | 2026-06-27 | dummy data added |
| 5 | 2026-06-27 | updated readme file |
| 6 | 2026-06-27 | otp limit in debug |

---

## 5. Hard evidence for metrics

| Metric | Status | Basis |
|--------|--------|-------|
| Test coverage % | **NOT EVIDENCED** | Zero test files. `find` for `tests.py` / `test_*.py` / `*_test.py` and `grep "def test_"` both return nothing. README *claims* a suite (`python manage.py test`) but there is **no backing code**. Do not put a coverage number on your resume. |
| Build / startup / performance data | **NOT EVIDENCED** | No benchmarks, no profiling output, no macrobenchmark module (Android concept, N/A), no gradle profile (no Gradle at all). |

---

## 6. Team-size signal

**Solo — one contributor** (`git shortlog`: `faruk` only). No `CODEOWNERS`, no
`AUTHORS` / contributor list. README says "Contributions are welcome / open
project", but there are no actual external contributors.

---

## 7. Resume-honesty notes

- **Vibe-coded.** The single ~4k-LOC "first commit", the polished
  section-referenced README (§9.1, §13.1, …), and the absence of iterative
  history or tests indicate AI-generated bulk code, not hand-written incremental
  engineering. Describe it as **AI-assisted / vibe-coded prototype**.
- **Do NOT claim** on this repo: test coverage %, CI/CD, performance/benchmarks,
  team collaboration, multi-module (Gradle) architecture, or DI — none evidenced.
- **Safe to claim:** designed and shipped a Django REST + PostGIS + Channels
  backend implementing a privacy-preserving geospatial discovery model, a
  JWT/OTP auth flow, and a server-enforced claim state machine with realtime
  chat — as a solo, AI-assisted prototype. Specific and defensible.

---

*All figures above are drawn directly from repo files and git history as of the
generation date. Items marked "not evidenced" have no supporting artifact in the
repository.*

---

## 8. Ready-to-paste resume bullets

Three variants at increasing "impressiveness" — but all stay within what the repo
evidences. Pick the level that matches how you want to represent the project;
none of them claim coverage %, CI, performance numbers, or team work.

### Variant A — Most conservative (fully AI-assisted framing)

> **NearAid — Mutual-Aid API** · Python, Django REST Framework, PostGIS, Channels
> - Built an AI-assisted prototype backend for a hyperlocal mutual-aid platform: a 9-app Django "modular monolith" (~4k LOC) covering auth, geo discovery, chat, claims, ratings, safety, and admin.
> - Implemented privacy-preserving geospatial discovery with GeoDjango/PostGIS — server-side point fuzzing (±300–500 m) and banded distances so exact coordinates are never exposed.
> - Modeled a server-enforced claim lifecycle state machine (open → claimed → delivered → completed) with realtime WebSocket chat over Django Channels/ASGI.

### Variant B — Balanced (recommended for a portfolio project)

> **NearAid — Hyperlocal Mutual-Aid Platform (Backend)** · Django REST Framework · PostGIS · Django Channels · JWT
> - Designed and shipped a solo backend prototype connecting people needing everyday aid with nearby helpers — 9 domain apps behind a single versioned API (`/v1`, `/admin/v1`, `/ws`), documented via OpenAPI/Swagger.
> - Engineered a privacy-first geospatial search on PostgreSQL + PostGIS (GeoDjango): dual `geography(Point,4326)` columns, GiST index, `ST_DWithin`/`ST_Distance`, with point-fuzzing and distance-banding so public endpoints never leak an exact location.
> - Built a phone-OTP → JWT auth flow (SimpleJWT) and a server-enforced claim state machine returning HTTP 409 on invalid transitions.
> - Added realtime 1:1 chat over Django Channels (ASGI) with claim-membership authorization and a Redis-backed channel layer.

### Variant C — Fullest (leads on system design; still evidence-safe)

> **NearAid — Mutual-Aid Marketplace API** · Python · Django/DRF · PostGIS · Channels · JWT · drf-spectacular
> - Architected a modular-monolith backend (9 Django apps, one per bounded context) exposing a mobile API and a staff admin API, with a consistent error envelope, cursor pagination, and rate limiting.
> - Delivered privacy-preserving geospatial discovery (GeoDjango + PostGIS) — jittered points and banded distances enforce that exact coordinates reach only the listing owner and active-claim counterpart.
> - Implemented a unified request/offer claim lifecycle as an explicit state machine with role-aware transitions (helper/recipient vs. seeker/giver) and two-way ratings feeding a trust score.
> - Stood up realtime chat via Django Channels/ASGI (WebSocket) with token auth and claim-scoped subscriptions, plus a runtime-tunable `PlatformConfig` and an immutable admin audit log.

> **Attribution note for interviews:** this is a solo, AI-assisted ("vibe-coded")
> prototype developed over ~2 days. It has no automated tests, CI, or benchmarks
> — be ready to say so if asked, and don't list those as accomplishments.
