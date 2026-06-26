"""
Push fan-out (§11). Localized to the recipient's language; respects blocks and
account status. In production each ``notify`` would enqueue a Celery task that
calls FCM for the recipient's devices; here it persists a Notification row (and
would be the natural place to hook the real FCM client).
"""
import logging

from .models import Device, Notification

logger = logging.getLogger("nearaid.push")

# title/body templates per type, per language (§11 "localized to recipient's language").
TEMPLATES = {
    Notification.Type.NEARBY_REQUEST: {
        "en": ("Someone nearby needs help", "{title}"),
        "bn": ("কাছেই কারও সাহায্য দরকার", "{title}"),
    },
    Notification.Type.NEARBY_OFFER: {
        "en": ("A neighbour is giving something away", "{title}"),
        "bn": ("পাশের কেউ কিছু দিচ্ছেন", "{title}"),
    },
    Notification.Type.REQUEST_CLAIMED: {
        "en": ("A helper claimed your request", "{title}"),
        "bn": ("একজন সাহায্যকারী আপনার অনুরোধ গ্রহণ করেছেন", "{title}"),
    },
    Notification.Type.OFFER_REQUESTED: {
        "en": ("Someone wants your offer", "{title}"),
        "bn": ("কেউ আপনার অফার চেয়েছেন", "{title}"),
    },
    Notification.Type.CHAT_MESSAGE: {
        "en": ("New message", "{title}"),
        "bn": ("নতুন বার্তা", "{title}"),
    },
    Notification.Type.CLAIM_DELIVERED: {
        "en": ("Marked delivered — please confirm", "{title}"),
        "bn": ("ডেলিভার করা হয়েছে — নিশ্চিত করুন", "{title}"),
    },
    Notification.Type.CLAIM_COMPLETED: {
        "en": ("Receipt confirmed — thanks!", "{title}"),
        "bn": ("রসিদ নিশ্চিত হয়েছে — ধন্যবাদ!", "{title}"),
    },
    Notification.Type.NEW_RATING: {
        "en": ("You received a new rating", "{title}"),
        "bn": ("আপনি একটি নতুন রেটিং পেয়েছেন", "{title}"),
    },
    Notification.Type.MODERATION: {
        "en": ("Update on your content", "{title}"),
        "bn": ("আপনার কনটেন্ট সম্পর্কে আপডেট", "{title}"),
    },
}


def notify(recipient, type, context=None, data=None):
    """Create + 'send' one notification to a single user."""
    context = context or {}
    data = data or {}
    if recipient.status != "active":
        return None
    lang = recipient.language if recipient.language in ("en", "bn") else "en"
    title_tpl, body_tpl = TEMPLATES.get(type, {}).get(lang, ("NearAid", "{title}"))
    notif = Notification.objects.create(
        recipient=recipient,
        type=type,
        title=title_tpl.format(**context)[:120],
        body=body_tpl.format(**context)[:255],
        data={**data, "type": type},
    )
    _push_to_devices(recipient, notif)
    return notif


def _push_to_devices(recipient, notif):
    """Stand-in for the FCM call. Logs the payload the Celery worker would send."""
    tokens = list(Device.objects.filter(user=recipient).values_list("fcm_token", flat=True))
    if not tokens:
        return
    payload = {
        "notification": {"title": notif.title, "body": notif.body},
        "data": {**notif.data, "deeplink": f"nearaid://{notif.data.get('type', '')}"},
    }
    logger.info("FCM → %s device(s): %s", len(tokens), payload)
