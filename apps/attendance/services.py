from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.school.models import Enrollment

from .models import Attendance, CheckEvent, Reason, Status


def events_for_day(enrollment, day):
    """Return immutable check events for one local calendar day."""
    start = timezone.make_aware(
        timezone.datetime.combine(day, timezone.datetime.min.time())
    )
    end = start + timezone.timedelta(days=1)
    return CheckEvent.objects.filter(
        enrollment=enrollment, occurred_at__gte=start, occurred_at__lt=end
    )


def event_time_for_day(day, group=None):
    """A deterministic local timestamp for a manual daily check-in.

    For today we retain the real click time. For historical corrections the
    group's opening time is used so reports never pretend the edit happened at
    the current clock time.
    """
    now = timezone.localtime()
    if day == now.date():
        return now
    opening = getattr(group, "opens_at", None) or timezone.datetime.min.time().replace(hour=9)
    return timezone.make_aware(timezone.datetime.combine(day, opening))


@transaction.atomic
def mark_daily_attendance(*, enrollment, day, value, user):
    """Single safe entry point for the daily attendance screen.

    IN/OUT events are immutable evidence. A daily summary may be edited only
    when that edit cannot contradict existing evidence.
    """
    events = events_for_day(enrollment, day)
    has_in = events.filter(kind=CheckEvent.Kind.IN).exists()
    has_out = events.filter(kind=CheckEvent.Kind.OUT).exists()

    if value == "clear":
        if has_in or has_out:
            raise ValidationError("Kirish/chiqish hodisasi bor kunni tozalab bo'lmaydi")
        Attendance.objects.filter(enrollment=enrollment, day=day).delete()
        return None

    if value in ("present", "late"):
        if has_in:
            event = events.filter(kind=CheckEvent.Kind.IN).order_by("occurred_at").first()
            local_time = timezone.localtime(event.occurred_at).time().replace(microsecond=0)
            mark, _ = Attendance.objects.update_or_create(
                enrollment=enrollment, day=day,
                defaults={"status": Status.PRESENT, "reason": "",
                          "arrived_at": local_time, "marked_by": user},
            )
            return mark
        check_in(
            enrollment=enrollment, user=user, method=CheckEvent.Method.MANUAL,
            occurred_at=event_time_for_day(day, enrollment.group),
            note="Kunlik davomat ekranidan belgilandi",
        )
        return Attendance.objects.get(enrollment=enrollment, day=day)

    if has_in or has_out:
        raise ValidationError("Check-in qilingan bolani 'kelmadi' deb belgilab bo'lmaydi")
    reason = value if value in dict(Reason.choices) else ""
    mark, _ = Attendance.objects.update_or_create(
        enrollment=enrollment, day=day,
        defaults={"status": Status.ABSENT, "reason": reason,
                  "arrived_at": None, "left_at": None, "marked_by": user},
    )
    return mark


def active_enrollment(child, at=None):
    day = timezone.localtime(at or timezone.now()).date()
    return (Enrollment.objects.filter(
        child=child, started_at__lte=day, is_paused=False,
    ).filter(models_q_open(day)).select_related("child", "group").first())


def models_q_open(day):
    from django.db.models import Q
    return Q(ended_at__isnull=True) | Q(ended_at__gte=day)


@transaction.atomic
def check_in(*, enrollment, user, method=CheckEvent.Method.MANUAL, occurred_at=None,
             note="", contact=None, idempotency_key=None, latitude=None,
             longitude=None, device_info="", synced_offline=False):
    if idempotency_key:
        existing = CheckEvent.objects.filter(idempotency_key=idempotency_key).first()
        if existing:
            return existing
    now = occurred_at or timezone.now()
    day = timezone.localtime(now).date()
    mark, _ = Attendance.objects.select_for_update().get_or_create(
        enrollment=enrollment, day=day,
        defaults={"status": Status.PRESENT, "marked_by": user},
    )
    if mark.arrived_at:
        raise ValidationError("Bola bugun allaqachon check-in qilingan")
    if mark.status == Status.ABSENT:
        mark.status, mark.reason = Status.PRESENT, ""
    mark.arrived_at = timezone.localtime(now).time().replace(microsecond=0)
    mark.marked_by = user
    mark.save(update_fields=["status", "reason", "arrived_at", "marked_by", "updated_at"])
    event = CheckEvent.objects.create(
        enrollment=enrollment, kind=CheckEvent.Kind.IN, occurred_at=now,
        method=method, recorded_by=user, note=note, contact=contact,
        idempotency_key=idempotency_key, latitude=latitude, longitude=longitude,
        device_info=device_info[:200], synced_offline=synced_offline,
    )
    from apps.school.telegram import notify_check_event
    notify_check_event(event)
    return event


@transaction.atomic
def check_out(*, enrollment, user, pickup_contact=None,
              method=CheckEvent.Method.MANUAL, occurred_at=None, note="",
              idempotency_key=None, latitude=None, longitude=None, device_info="",
              synced_offline=False, override_by=None, override_reason=""):
    if idempotency_key:
        existing = CheckEvent.objects.filter(idempotency_key=idempotency_key).first()
        if existing:
            return existing
    now = occurred_at or timezone.now()
    day = timezone.localtime(now).date()
    try:
        mark = Attendance.objects.select_for_update().get(enrollment=enrollment, day=day)
    except Attendance.DoesNotExist as exc:
        raise ValidationError("Check-outdan oldin bola check-in qilinishi kerak") from exc
    if mark.status != Status.PRESENT or not mark.arrived_at:
        raise ValidationError("Check-outdan oldin bola check-in qilinishi kerak")
    if mark.left_at:
        raise ValidationError("Bola bugun allaqachon check-out qilingan")
    if pickup_contact and pickup_contact.child_id != enrollment.child_id:
        raise ValidationError("Olib ketuvchi bu bolaga tegishli emas")
    allowed = bool(pickup_contact and pickup_contact.can_pickup)
    if pickup_contact and not allowed and not override_by:
        raise ValidationError("Bu odam bolani olib ketishga ruxsat etilmagan")
    if not pickup_contact and enrollment.child.contacts.filter(can_pickup=True).exists() and not override_by:
        raise ValidationError("Olib ketuvchi shaxsni tanlash kerak")
    if not pickup_contact and not note.strip() and not override_by:
        raise ValidationError("Olib ketuvchi ro'yxatda bo'lmasa, izoh majburiy")
    if override_by and not override_reason.strip():
        raise ValidationError("Direktor ruxsati sababi majburiy")
    mark.left_at = timezone.localtime(now).time().replace(microsecond=0)
    mark.marked_by = user
    mark.save(update_fields=["left_at", "marked_by", "updated_at"])
    event = CheckEvent.objects.create(
        enrollment=enrollment, kind=CheckEvent.Kind.OUT, occurred_at=now,
        method=method, pickup_contact=pickup_contact, contact=pickup_contact,
        recorded_by=user, note=note, idempotency_key=idempotency_key,
        latitude=latitude, longitude=longitude, device_info=device_info[:200],
        synced_offline=synced_offline, is_override=bool(override_by),
        override_by=override_by, override_reason=override_reason,
    )
    from apps.school.telegram import notify_check_event
    notify_check_event(event)
    return event
