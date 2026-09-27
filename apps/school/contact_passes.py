import hashlib
import hmac
import random
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from .models import ContactPass, Person
from .phones import normalize_phone


def _signature(payload):
    return hmac.new(settings.SECRET_KEY.encode(), payload.encode(), hashlib.sha256).hexdigest()


def issue_contact_pass(contact_or_person):
    person = getattr(contact_or_person, "person", contact_or_person)
    now = timezone.now()
    while True:
        code = f"{random.SystemRandom().randrange(100000, 1000000)}"
        if not ContactPass.objects.filter(code=code, expires_at__gt=now, used_at__isnull=True).exists():
            break
    item = ContactPass.objects.create(
        person=person, code=code, qr_expires_at=now + timedelta(seconds=60),
        expires_at=now + timedelta(minutes=5),
    )
    payload = f"p1.{person.id}.{int(item.qr_expires_at.timestamp())}.{item.id}"
    return item, f"{payload}.{_signature(payload)}"


def resolve_signed_token(token, allow_offline_grace=False):
    parts = (token or "").split(".")
    if len(parts) != 5 or parts[0] != "p1":
        return None
    payload, signature = ".".join(parts[:4]), parts[4]
    if not hmac.compare_digest(_signature(payload), signature):
        return None
    try:
        expires = int(parts[2])
        item = ContactPass.objects.select_related("person__kindergarten").get(
            id=parts[3], person_id=parts[1], used_at__isnull=True
        )
    except (ValueError, ContactPass.DoesNotExist):
        return None
    grace = 86400 if allow_offline_grace else 0
    if int(timezone.now().timestamp()) > expires + grace:
        return None
    return item


def resolve_code(code):
    return ContactPass.objects.select_related("person__kindergarten").filter(
        code=code, expires_at__gt=timezone.now(), used_at__isnull=True
    ).order_by("-created_at").first()


def sibling_contacts(contact_or_person):
    person = getattr(contact_or_person, "person", contact_or_person)
    return list(person.contacts.select_related("child", "person").filter(
        child__kindergarten=person.kindergarten))
