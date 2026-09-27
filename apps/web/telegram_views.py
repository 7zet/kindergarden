import json
import uuid
import hashlib
import hmac
import time
from datetime import datetime
from urllib.parse import parse_qsl

from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from apps.attendance.models import Attendance
from apps.school.models import PickupPass, TelegramAccount, TelegramLinkCode
from apps.school.telegram import create_pickup_pass, send_message, send_staff_message
from apps.billing.services import child_balance
from django.shortcuts import render
from django.db import transaction
from django.db.models import Q
from django.core.exceptions import ValidationError

from apps.accounts.models import User
from apps.attendance.models import CheckEvent
from apps.attendance.services import check_in, check_out
from apps.school.contact_passes import (issue_contact_pass, resolve_code,
                                        resolve_signed_token, sibling_contacts,
                                        normalize_phone)
from apps.school.models import (Contact, Enrollment, Person, StaffTelegramAccount,
                                StaffTelegramLinkCode)
from apps.web.access import CHECK_IN, CHECK_OUT, MANUAL_CHECK, VIEW_ALL_GROUPS


@csrf_exempt
def webhook(request):
    if request.method != "POST":
        return JsonResponse({"ok": True})
    if (settings.TELEGRAM_WEBHOOK_SECRET and
            request.headers.get("X-Telegram-Bot-Api-Secret-Token") != settings.TELEGRAM_WEBHOOK_SECRET):
        return JsonResponse({"ok": False}, status=403)
    try:
        update = json.loads(request.body)
        message = update.get("message") or {}
        text = (message.get("text") or "").strip()
        chat_id = message["chat"]["id"]
        user_id = message["from"]["id"]
    except (ValueError, KeyError, TypeError):
        return JsonResponse({"ok": True})

    if text.startswith("/start staff_"):
        try:
            token = uuid.UUID(text.removeprefix("/start staff_"))
            code = StaffTelegramLinkCode.objects.select_related("user").get(token=token)
        except (ValueError, StaffTelegramLinkCode.DoesNotExist):
            send_message(chat_id, "Xodim ulash kodi noto'g'ri.")
            return JsonResponse({"ok": True})
        if not code.is_valid:
            send_message(chat_id, "Xodim ulash kodi eskirgan yoki ishlatilgan.")
            return JsonResponse({"ok": True})
        StaffTelegramAccount.objects.update_or_create(
            user=code.user, defaults={"telegram_user_id": user_id, "chat_id": chat_id,
                                      "is_active": True}
        )
        code.used_at = timezone.now(); code.save(update_fields=["used_at"])
        send_staff_message(chat_id, f"✅ {code.user.full_name}, xodim Mini App hisobingiz ulandi.")
        return JsonResponse({"ok": True})

    if text.startswith("/start "):
        try:
            token = uuid.UUID(text.split(maxsplit=1)[1])
            code = TelegramLinkCode.objects.select_related("contact__child", "contact__person").get(token=token)
        except (ValueError, TelegramLinkCode.DoesNotExist):
            send_message(chat_id, "Ulash kodi noto'g'ri yoki topilmadi.")
            return JsonResponse({"ok": True})
        if not code.is_valid:
            send_message(chat_id, "Ulash kodi eskirgan yoki ishlatilgan.")
            return JsonResponse({"ok": True})
        account, _ = TelegramAccount.objects.get_or_create(
            telegram_user_id=user_id, defaults={"chat_id": chat_id}
        )
        account.chat_id, account.is_active = chat_id, True
        account.save(update_fields=["chat_id", "is_active"])
        account.persons.add(code.contact.person)
        code.used_at = timezone.now()
        code.save(update_fields=["used_at"])
        send_message(chat_id, f"✅ {code.contact.child.full_name} profiliga muvaffaqiyatli ulandingiz.")
        return JsonResponse({"ok": True})

    account = TelegramAccount.objects.filter(telegram_user_id=user_id, is_active=True).first()
    if not account:
        send_message(chat_id, "Avval bog'cha bergan maxsus havola orqali profilingizni ulang.")
        return JsonResponse({"ok": True})
    contacts = list(Contact.objects.filter(person__telegram_accounts=account)
                    .select_related("child", "person").distinct())
    if text in ("/start", "👶 Farzandlarim"):
        send_message(chat_id, "👶 Farzandlaringiz:\n" + "\n".join(
            f"• {c.child.full_name}" for c in contacts
        ))
    elif text == "✅ Bugungi davomat":
        lines = []
        for contact in contacts:
            mark = Attendance.objects.filter(
                enrollment__child=contact.child, day=timezone.localdate()
            ).first()
            if not mark:
                state = "belgilanmagan"
            elif mark.left_at:
                state = f"{mark.arrived_at:%H:%M} keldi, {mark.left_at:%H:%M} ketdi"
            elif mark.arrived_at:
                state = f"{mark.arrived_at:%H:%M} dan bog'chada"
            else:
                state = mark.get_status_display()
            lines.append(f"• {contact.child.full_name}: {state}")
        send_message(chat_id, "✅ Bugungi davomat:\n" + "\n".join(lines))
    elif text == "🔐 Olib ketish QR":
        lines = []
        for contact in contacts:
            if not contact.can_pickup:
                continue
            pickup_pass = create_pickup_pass(contact)
            lines.append(
                f"{contact.child.full_name}: {settings.PUBLIC_BASE_URL}/telegram/pickup/{pickup_pass.token}/"
            )
        send_message(chat_id, "🔐 60 soniya amal qiladigan QR:\n" + (
            "\n".join(lines) if lines else "Sizda olib ketish ruxsati yo'q."
        ), keyboard=True)
    else:
        send_message(chat_id, "Quyidagi menyudan kerakli bo'limni tanlang.")
    return JsonResponse({"ok": True})


def pickup_qr(request, token):
    pickup_pass = PickupPass.objects.filter(token=token).first()
    if not pickup_pass or not pickup_pass.is_valid:
        return HttpResponse("QR eskirgan yoki ishlatilgan", status=410)
    import qrcode
    import qrcode.image.svg
    image = qrcode.make(
        f"pickup:{pickup_pass.token}", image_factory=qrcode.image.svg.SvgPathImage,
        box_size=9, border=2,
    )
    response = HttpResponse(content_type="image/svg+xml")
    image.save(response)
    response["Cache-Control"] = "no-store"
    return response


def contact_qr(request):
    token = request.GET.get("token", "")
    if not resolve_signed_token(token):
        return HttpResponse("QR eskirgan", status=410)
    import qrcode
    import qrcode.image.svg
    image = qrcode.make(token, image_factory=qrcode.image.svg.SvgPathImage,
                        box_size=9, border=2)
    response = HttpResponse(content_type="image/svg+xml")
    image.save(response); response["Cache-Control"] = "no-store"
    return response


def mini_app(request):
    return render(request, "telegram/mini_app.html")


def _telegram_user(init_data):
    values = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = values.pop("hash", "")
    try:
        auth_date = int(values.get("auth_date", "0"))
    except (ValueError, TypeError):
        return None
    if not received_hash or abs(int(time.time()) - auth_date) > 3600:
        return None
    check_string = "\n".join(f"{key}={values[key]}" for key in sorted(values))
    secret = hmac.new(b"WebAppData", settings.TELEGRAM_BOT_TOKEN.encode(), hashlib.sha256).digest()
    calculated = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(calculated, received_hash):
        return None
    try:
        return json.loads(values["user"])
    except (KeyError, ValueError, TypeError):
        return None


@csrf_exempt
def mini_session(request):
    if request.method != "POST" or not settings.TELEGRAM_BOT_TOKEN:
        return JsonResponse({"error": "Mini App sozlanmagan"}, status=400)
    try:
        init_data = json.loads(request.body).get("initData", "")
    except ValueError:
        return JsonResponse({"error": "Noto'g'ri so'rov"}, status=400)
    telegram_user = _telegram_user(init_data)
    if not telegram_user:
        return JsonResponse({"error": "Telegram imzosi tasdiqlanmadi"}, status=403)
    account = TelegramAccount.objects.filter(
        telegram_user_id=telegram_user["id"], is_active=True
    ).first()
    if not account:
        return JsonResponse({"error": "Profil bog'chaga ulanmagan"}, status=403)
    children, seen = [], set()
    persons = list(account.persons.prefetch_related("contacts__child").all())
    all_contacts = [contact for person in persons for contact in sibling_contacts(person)]
    for contact in all_contacts:
        child = contact.child
        if child.id in seen:
            continue
        seen.add(child.id)
        mark = Attendance.objects.filter(
            enrollment__child=child, day=timezone.localdate()
        ).first()
        if not mark:
            attendance = "Belgilanmagan"
        elif mark.left_at:
            attendance = f"{mark.arrived_at:%H:%M} keldi · {mark.left_at:%H:%M} ketdi"
        elif mark.arrived_at:
            attendance = f"{mark.arrived_at:%H:%M} dan bog'chada"
        else:
            attendance = mark.get_status_display()
        children.append({
            "id": str(child.id), "name": child.full_name,
            "group": child.current_enrollment.group.name if child.current_enrollment else "—",
            "attendance": attendance, "balance": str(child_balance(child)),
            "canPickup": contact.can_pickup,
        })
    return JsonResponse({"user": telegram_user, "children": children,
        "contacts": [{"id": str(p.id), "name": p.full_name,
                      "relation": ", ".join(sorted(set(
                          p.contacts.values_list("relation", flat=True))))} for p in persons]})


def _body(request):
    try:
        return json.loads(request.body)
    except (ValueError, TypeError):
        return {}


def _parent_account(data):
    telegram_user = _telegram_user(data.get("initData", ""))
    if not telegram_user:
        return None
    return TelegramAccount.objects.filter(
        telegram_user_id=telegram_user["id"], is_active=True
    ).first()


def _staff(data):
    telegram_user = _telegram_user(data.get("initData", ""))
    if not telegram_user:
        return None
    link = StaffTelegramAccount.objects.select_related("user__kindergarten").filter(
        telegram_user_id=telegram_user["id"], is_active=True
    ).first()
    return link.user if link else None


@csrf_exempt
def parent_credential(request):
    data = _body(request)
    account = _parent_account(data)
    if not account:
        return JsonResponse({"error": "Telegram hisobi tasdiqlanmadi"}, status=403)
    person = account.persons.filter(id=data.get("contactId")).first()
    if not person:
        return JsonResponse({"error": "Kontakt topilmadi"}, status=404)
    item, token = issue_contact_pass(person)
    return JsonResponse({
        "token": token, "code": item.code,
        "qrExpiresAt": item.qr_expires_at.isoformat(),
        "codeExpiresAt": item.expires_at.isoformat(),
        "contact": {"id": str(person.id), "name": person.full_name,
                    "relation": ", ".join(sorted(set(
                        person.contacts.values_list("relation", flat=True))))},
    })


def _visible_enrollments(user, contacts):
    today = timezone.localdate()
    groups = Enrollment.objects.filter(
        child__contacts__in=contacts, started_at__lte=today, is_paused=False,
    ).filter(Q(ended_at__isnull=True) | Q(ended_at__gte=today))
    if not user.has_perm(VIEW_ALL_GROUPS):
        groups = groups.filter(group__teachers=user)
    return groups.select_related("child", "group").distinct()


def _resolve_for_staff(user, data, offline=False):
    item = (resolve_code(str(data.get("code", "")).strip()) if data.get("code")
            else resolve_signed_token(data.get("token", ""), allow_offline_grace=offline))
    if not item:
        return None, None, []
    if item.person.kindergarten_id != user.kindergarten_id:
        return None, None, []
    contacts = sibling_contacts(item.person)
    by_child = {c.child_id: c for c in contacts}
    enrollments = _visible_enrollments(user, contacts)
    children = []
    for enrollment in enrollments:
        contact = by_child[enrollment.child_id]
        mark = Attendance.objects.filter(enrollment=enrollment, day=timezone.localdate()).first()
        children.append({
            "enrollmentId": str(enrollment.id), "contactId": str(contact.id),
            "name": enrollment.child.full_name, "group": enrollment.group.name,
            "allergies": enrollment.child.allergies, "healthNote": enrollment.child.health_note,
            "canPickup": contact.can_pickup,
            "inside": bool(mark and mark.arrived_at and not mark.left_at),
            "arrivedAt": mark.arrived_at.strftime("%H:%M") if mark and mark.arrived_at else None,
        })
    return item, item.person, children


@csrf_exempt
def staff_resolve(request):
    data = _body(request); user = _staff(data)
    if not user:
        return JsonResponse({"error": "Xodim Telegram hisobi ulanmagan"}, status=403)
    item, contact, children = _resolve_for_staff(user, data, bool(data.get("offline")))
    if not item:
        return JsonResponse({"error": "QR/kod noto'g'ri, eskirgan yoki ishlatilgan"}, status=410)
    kind = data.get("kind", "in")
    permitted = user.has_perm(CHECK_IN if kind == "in" else CHECK_OUT)
    return JsonResponse({
        "credentialId": str(item.id), "permitted": permitted,
        "person": {"name": contact.full_name,
                   "relation": ", ".join(sorted(set(
                       contact.contacts.values_list("relation", flat=True)))),
                   "phone": contact.phone}, "children": children,
        "canOverride": user.has_perm("attendance.override_check_child"),
    })


@csrf_exempt
@transaction.atomic
def staff_confirm(request):
    data = _body(request); user = _staff(data)
    if not user:
        return JsonResponse({"error": "Xodim Telegram hisobi ulanmagan"}, status=403)
    offline = bool(data.get("offline"))
    item, _, resolved = _resolve_for_staff(user, data, offline)
    if not item:
        return JsonResponse({"error": "QR/kod eskirgan yoki ishlatilgan"}, status=410)
    selected = set(data.get("enrollmentIds") or [])
    rows = [row for row in resolved if row["enrollmentId"] in selected]
    if not rows:
        return JsonResponse({"error": "Kamida bitta bola tanlang"}, status=400)
    kind = data.get("kind")
    permission = CHECK_IN if kind == "in" else CHECK_OUT
    if not user.has_perm(permission):
        return JsonResponse({"error": "Bu amal uchun ruxsat yo'q"}, status=403)
    override_reason = (data.get("overrideReason") or "").strip()
    if kind == "out" and any(not row["canPickup"] for row in rows):
        if not user.has_perm("attendance.override_check_child") or not override_reason:
            return JsonResponse({"error": "Bu odam olib ketishga ruxsat etilmagan"}, status=403)
    events = []
    occurred_at = None
    if offline and data.get("scannedAt"):
        try:
            occurred_at = datetime.fromisoformat(
                data["scannedAt"].replace("Z", "+00:00")
            )
            if abs((timezone.now() - occurred_at).total_seconds()) > 86400:
                return JsonResponse({"error": "Offline yozuv 24 soatdan eski"}, status=410)
        except (ValueError, TypeError):
            return JsonResponse({"error": "Offline vaqt noto'g'ri"}, status=400)
    for row in rows:
        enrollment = Enrollment.objects.select_related("child").get(id=row["enrollmentId"])
        contact = Contact.objects.get(id=row["contactId"])
        common = dict(
            enrollment=enrollment, user=user, method=CheckEvent.Method.PARENT_PASS,
            idempotency_key=data.get("idempotency", {}).get(row["enrollmentId"]),
            latitude=data.get("latitude"), longitude=data.get("longitude"),
            device_info=data.get("device", ""), synced_offline=offline,
            occurred_at=occurred_at,
        )
        try:
            event = (check_in(contact=contact, **common) if kind == "in" else
                     check_out(pickup_contact=contact,
                               override_by=user if not contact.can_pickup else None,
                               override_reason=override_reason, **common))
        except ValidationError as exc:
            transaction.set_rollback(True)
            return JsonResponse({"error": "; ".join(exc.messages)}, status=409)
        events.append(str(event.id))
    item.used_at = timezone.now(); item.save(update_fields=["used_at"])
    return JsonResponse({"ok": True, "events": events, "count": len(events)})


def staff_mini_app(request):
    return render(request, "telegram/staff_app.html")


@csrf_exempt
def staff_bootstrap(request):
    data = _body(request); user = _staff(data)
    if not user:
        return JsonResponse({"error": "Xodim Telegram hisobi ulanmagan"}, status=403)
    today = timezone.localdate()
    enrollments = Enrollment.objects.filter(
        group__kindergarten=user.kindergarten, started_at__lte=today, is_paused=False,
    ).filter(Q(ended_at__isnull=True) | Q(ended_at__gte=today)).select_related(
        "child", "group"
    ).prefetch_related("child__contacts")
    if not user.has_perm(VIEW_ALL_GROUPS):
        enrollments = enrollments.filter(group__teachers=user)
    enrollments = list(enrollments)
    marks = {a.enrollment_id: a for a in Attendance.objects.filter(
        enrollment__in=enrollments, day=today)}
    entries, person_groups = {}, {}
    for enrollment in enrollments:
        for contact in enrollment.child.contacts.all():
            person_groups.setdefault(contact.person_id, []).append(
                (contact, enrollment)
            )
    for person_id, pairs in person_groups.items():
        children = [{"enrollmentId": str(e.id), "contactId": str(c.id),
            "name": e.child.full_name, "group": e.group.name,
            "allergies": e.child.allergies, "healthNote": e.child.health_note,
            "canPickup": c.can_pickup,
            "inside": bool(marks.get(e.id) and marks[e.id].arrived_at and not marks[e.id].left_at),
            "arrivedAt": marks[e.id].arrived_at.strftime("%H:%M") if marks.get(e.id) and marks[e.id].arrived_at else None}
            for c, e in pairs]
        contact = pairs[0][0]
        entries[str(person_id)] = {"credentialId": "offline",
            "permitted": True, "canOverride": user.has_perm("attendance.override_check_child"),
            "person": {"name": contact.full_name,
                       "relation": ", ".join(sorted(set(c.relation for c, _ in pairs))),
                       "phone": contact.phone}, "children": children}
    return JsonResponse({"generatedAt": timezone.now().isoformat(), "contacts": entries})
