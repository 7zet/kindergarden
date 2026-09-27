"""Ariza bilan bog'liq operatsiyalar."""

from django.db import transaction
from datetime import date, timedelta


def _overlapping_enrollments(*, child=None, group=None, started_at, ended_at=None,
                             exclude_id=None):
    """Inclusive date intervals that overlap the requested contract period."""
    from django.db.models import Q
    from .models import Enrollment

    qs = Enrollment.objects.all()
    if child is not None:
        qs = qs.filter(child=child)
    if group is not None:
        qs = qs.filter(group=group)
    if exclude_id:
        qs = qs.exclude(pk=exclude_id)
    if ended_at:
        qs = qs.filter(started_at__lte=ended_at)
    return qs.filter(Q(ended_at__isnull=True) | Q(ended_at__gte=started_at))


def _group_has_capacity(*, group, started_at, ended_at=None, exclude_id=None):
    """Davrning istalgan kunida sig'im oshib ketishini aniqlaydi."""
    if group.capacity < 1:
        return False
    events = {}
    requested_end = ended_at or date.max
    for enrollment in _overlapping_enrollments(
            group=group, started_at=started_at, ended_at=ended_at,
            exclude_id=exclude_id).only("started_at", "ended_at"):
        overlap_start = max(started_at, enrollment.started_at)
        overlap_end = min(requested_end, enrollment.ended_at or date.max)
        events[overlap_start] = events.get(overlap_start, 0) + 1
        if overlap_end < date.max:
            next_day = overlap_end + timedelta(days=1)
            events[next_day] = events.get(next_day, 0) - 1
    occupied = 0
    for _, delta in sorted(events.items()):
        occupied += delta
        if occupied >= group.capacity:
            return False
    return True


@transaction.atomic
def create_enrollment(*, child, group, tariff, started_at, ended_at=None,
                      discount=None):
    """Shartnomani overlap va sig'imni atomar tekshirib yaratadi."""
    from django.core.exceptions import ValidationError
    from .models import Child, Enrollment, Group

    Child.objects.select_for_update().get(pk=child.pk)
    Group.objects.select_for_update().get(pk=group.pk)
    if _overlapping_enrollments(child=child, started_at=started_at,
                                ended_at=ended_at).exists():
        raise ValidationError("Bu bolada tanlangan davr bilan kesishadigan shartnoma mavjud.")
    if not _group_has_capacity(group=group, started_at=started_at,
                               ended_at=ended_at):
        raise ValidationError("Tanlangan davrda guruhda bo'sh joy yo'q.")
    enrollment = Enrollment(child=child, group=group, tariff=tariff,
                            discount=discount, started_at=started_at,
                            ended_at=ended_at)
    enrollment.full_clean()
    enrollment.save()
    return enrollment


@transaction.atomic
def transfer_enrollment(*, enrollment, new_group, new_tariff, effective_date, discount=None):
    """Eski shartnomani yopib, yangisini bitta transactionda ochadi."""
    from django.core.exceptions import ValidationError
    from .models import Enrollment

    old = Enrollment.objects.select_for_update().select_related("child", "group").get(pk=enrollment.pk)
    if not old.is_open:
        raise ValidationError("Yopilgan shartnomani ko'chirib bo'lmaydi")
    if new_group.kindergarten_id != old.child.kindergarten_id or new_tariff.kindergarten_id != old.child.kindergarten_id:
        raise ValidationError("Guruh va tarif shu bog'chaga tegishli bo'lishi kerak")
    if effective_date <= old.started_at:
        raise ValidationError("Ko'chirish sanasi shartnoma boshlangan sanadan keyin bo'lishi kerak")
    if _overlapping_enrollments(child=old.child, started_at=effective_date,
                                exclude_id=old.pk).exists():
        raise ValidationError("Bolada ko'chirish sanasi bilan kesishadigan boshqa shartnoma mavjud")
    if not _group_has_capacity(group=new_group, started_at=effective_date,
                               exclude_id=old.pk):
        raise ValidationError("Yangi guruhda bo'sh joy yo'q")
    old.ended_at = effective_date - timedelta(days=1)
    old.end_reason = Enrollment.EndReason.TRANSFERRED
    old.save(update_fields=["ended_at", "end_reason"])
    new = Enrollment(child=old.child, group=new_group, tariff=new_tariff,
                     discount=discount, started_at=effective_date)
    new.full_clean()
    new.save()
    return new

from apps.accounts.audit import log as audit

from .models import Application, Child, Contact, Enrollment


@transaction.atomic
def accept_application(application, *, group, tariff, started_at,
                       discount=None, user=None):
    """Arizani qabul qiladi: Child va Enrollment yaratadi.
    Shu paytdan boshlab pul hisoblanadi."""
    if application.status == Application.Status.ACCEPTED:
        return application.child

    child = application.child or Child.objects.create(
        kindergarten=application.kindergarten,
        full_name=application.child_name,
        birth_date=application.birth_date,
    )
    Contact.objects.get_or_create(
        child=child, phone=application.parent_phone,
        defaults={
            "full_name": application.parent_name or "Ota-ona",
            "relation": "Ota-ona",
            "kind": Contact.Kind.PARENT,
            "is_primary": True,
            "is_payer": True,
            "can_pickup": True,
            "has_app_access": True,
            "can_see_billing": True,
            "receives_messages": True,
        },
    )
    create_enrollment(child=child, group=group, tariff=tariff,
                      discount=discount, started_at=started_at)
    application.child = child
    application.status = Application.Status.ACCEPTED
    application.save(update_fields=["child", "status", "updated_at"])
    audit("application.accept", application,
          note=f"{child.full_name} → {group.name}", user=user)
    return child


@transaction.atomic
def end_enrollment(enrollment, *, ended_at, reason, user=None):
    """Shartnomani yopadi. O'chirmaydi — tarix saqlanadi."""
    enrollment.ended_at = ended_at
    enrollment.end_reason = reason
    enrollment.is_paused = False
    enrollment.save(update_fields=["ended_at", "end_reason", "is_paused"])
    audit("enrollment.end", enrollment,
          note=f"{enrollment.child.full_name}: {enrollment.get_end_reason_display()}",
          user=user)
    return enrollment


@transaction.atomic
def toggle_pause(enrollment, *, paused, note="", user=None):
    enrollment.is_paused = paused
    enrollment.pause_note = note if paused else ""
    enrollment.save(update_fields=["is_paused", "pause_note"])
    audit("enrollment.pause" if paused else "enrollment.resume",
          enrollment, note=note, user=user)
    return enrollment
