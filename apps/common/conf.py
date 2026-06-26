"""
Live platform configuration accessor (§12 Configuration).

The admin panel stores tunables (request TTL, offer window, fuzz radius,
auto-hide threshold) in a single ``PlatformConfig`` row. Everywhere else reads
them through ``platform_conf()`` so an admin's ``PATCH /admin/v1/config`` takes
effect without a redeploy. Falls back to ``settings.NEARAID`` before the row
exists (fresh DB, migrations).
"""
from django.conf import settings


def platform_conf():
    """Return the live PlatformConfig row, or a settings-backed stand-in."""
    try:
        from apps.adminpanel.models import PlatformConfig

        return PlatformConfig.load()
    except Exception:  # table not migrated yet, etc.
        return _SettingsConf()


class _SettingsConf:
    """Read-only view over settings.NEARAID matching PlatformConfig's attributes."""

    _N = settings.NEARAID

    request_ttl_days = _N["REQUEST_TTL_DAYS"]
    offer_default_window_hours = _N["OFFER_DEFAULT_WINDOW_HOURS"]
    fuzz_radius_m = _N["FUZZ_RADIUS_M"]
    auto_hide_reports = _N["AUTO_HIDE_REPORTS"]
