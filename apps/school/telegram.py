import json
import logging
from datetime import timedelta
from urllib.request import Request, urlopen

from django.conf import settings
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)


def api_call(method, payload):
    if not settings.TELEGRAM_BOT_TOKEN:
        return None
    request = Request(
        f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/{method}",
        data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"},
    )
    try:
        with urlopen(request, timeout=8) as response:
            return json.loads(response.read())
    except Exception:
        logger.exception("Telegram API xatosi")
        return None


def send_message(chat_id, text, keyboard=True):
    payload = {"chat_id": chat_id, "text": text}
    if keyboard:
        payload["reply_markup"] = {"keyboard": [
            [{"text": "👶 Farzandlarim"}, {"text": "✅ Bugungi davomat"}],
            [{"text": "🔐 QR ko'rsatish", "web_app": {"url": settings.TELEGRAM_MINI_APP_URL}}],
        ], "resize_keyboard": True}
    return api_call("sendMessage", payload)


def send_staff_message(chat_id, text):
    return api_call("sendMessage", {"chat_id": chat_id, "text": text,
        "reply_markup": {"keyboard": [[{"text": "📷 Skanerlash",
        "web_app": {"url": settings.TELEGRAM_STAFF_APP_URL}}]], "resize_keyboard": True}})


def notify_check_event(event):
    from apps.operations.services import queue_check_event
    queue_check_event(event)


def create_pickup_pass(contact):
    from .models import PickupPass
    return PickupPass.objects.create(
        child=contact.child, contact=contact,
        expires_at=timezone.now() + timedelta(seconds=60),
    )
