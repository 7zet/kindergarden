from datetime import timedelta
from decimal import Decimal

from celery import shared_task
from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone

from apps.attendance.models import Attendance, CheckEvent, Status
from apps.billing.models import Invoice, Payment
from apps.billing.services import generate_invoices
from apps.school.models import (Kindergarten, StaffTelegramAccount,
                                TelegramAccount, WorkingCalendar)
from apps.school.telegram import send_message

from .models import (Announcement, Expense, NotificationOutbox, PayrollEntry,
                     ServiceHeartbeat)
from .services import enqueue, enqueue_for_child


@shared_task
def record_worker_heartbeat():
    ServiceHeartbeat.objects.update_or_create(
        service="celery", defaults={"seen_at": timezone.now(), "details": {"ok": True}})
    return True


@shared_task
def deliver_notification_outbox(batch_size=100):
    now = timezone.now()
    ids = list(NotificationOutbox.objects.filter(
        status__in=[NotificationOutbox.Status.PENDING, NotificationOutbox.Status.FAILED],
        available_at__lte=now, attempts__lt=8).values_list("id", flat=True)[:batch_size])
    sent = failed = 0
    for item_id in ids:
        with transaction.atomic():
            item = NotificationOutbox.objects.select_for_update().get(pk=item_id)
            if item.status == NotificationOutbox.Status.SENT or item.available_at > now:
                continue
            item.status = NotificationOutbox.Status.SENDING
            item.attempts += 1
            item.save(update_fields=["status", "attempts"])
        result = send_message(item.chat_id, item.text)
        if result and result.get("ok"):
            item.status, item.sent_at, item.last_error = NotificationOutbox.Status.SENT, timezone.now(), ""
            sent += 1
        else:
            item.status = NotificationOutbox.Status.FAILED
            item.available_at = timezone.now() + timedelta(minutes=min(60, 2 ** item.attempts))
            item.last_error = "Telegram API javobi olinmadi"
            failed += 1
        item.save(update_fields=["status", "sent_at", "last_error", "available_at"])
    return {"sent": sent, "failed": failed}


def _money(value):
    return f"{value:,.0f}".replace(",", " ")


@shared_task
def daily_business_automation():
    today, tomorrow = timezone.localdate(), timezone.localdate() + timedelta(days=1)
    now = timezone.now()
    for kg in Kindergarten.objects.filter(is_active=True):
        # To'lov muddati va qarzdorlik eslatmalari.
        invoices = Invoice.objects.filter(kindergarten=kg).unpaid().select_related("enrollment__child")
        for invoice in invoices:
            if invoice.due_at == tomorrow or invoice.due_at < today:
                child = invoice.enrollment.child
                overdue = (today - invoice.due_at).days
                label = ("To'lov muddati ertaga" if overdue < 0 else
                         f"To'lov {overdue} kun kechikdi")
                text = (f"⚠️ {label}. {child.full_name}: "
                        f"{_money(invoice.balance)} so'm qoldiq. Invoys: {invoice.number}")
                enqueue_for_child(child, kind="debt_reminder", text=text,
                                  dedupe_prefix=f"debt:{invoice.id}:{today}", billing=True)

        # Ertangi maxsus dam olish kuni.
        calendar = WorkingCalendar.objects.filter(kindergarten=kg, day=tomorrow,
                                                  is_working=False).first()
        if calendar:
            text = f"📅 Eslatma: {tomorrow:%d.%m.%Y} — dam olish kuni. {calendar.note}"
            for account in TelegramAccount.objects.filter(
                    persons__contacts__child__kindergarten=kg, is_active=True).distinct():
                enqueue(kindergarten=kg, chat_id=account.chat_id, kind="calendar",
                        text=text, dedupe_key=f"calendar:{kg.id}:{tomorrow}:{account.chat_id}")

        # Rahbarga kun yakuni.
        income = Payment.objects.filter(kindergarten=kg, is_reversed=False,
                                        received_at__date=today).aggregate(s=Sum("amount"))["s"] or Decimal("0")
        expense = Expense.objects.filter(kindergarten=kg, is_void=False,
                                         paid_at__date=today).aggregate(s=Sum("amount"))["s"] or Decimal("0")
        present = Attendance.objects.filter(enrollment__group__kindergarten=kg,
                                            day=today, status=Status.PRESENT).count()
        arrived = CheckEvent.objects.filter(enrollment__group__kindergarten=kg,
                                            occurred_at__date=today, kind="in").count()
        left = CheckEvent.objects.filter(enrollment__group__kindergarten=kg,
                                         occurred_at__date=today, kind="out").count()
        debt = sum((i.balance for i in Invoice.objects.filter(kindergarten=kg).unpaid()), Decimal("0"))
        text = (f"📊 {today:%d.%m.%Y} kun yakuni\n"
                f"Tushum: {_money(income)} so'm\nXarajat: {_money(expense)} so'm\n"
                f"Kunlik natija: {_money(income-expense)} so'm\n"
                f"Davomat: {present} bola · kirish {arrived} · chiqish {left}\n"
                f"Jami qarzdorlik: {_money(debt)} so'm")
        leaders = StaffTelegramAccount.objects.filter(
            user__kindergarten=kg, user__is_owner=True, is_active=True)
        for leader in leaders:
            enqueue(kindergarten=kg, chat_id=leader.chat_id, kind="daily_summary", text=text,
                    dedupe_key=f"daily-summary:{kg.id}:{today}:{leader.chat_id}")
    deliver_notification_outbox.delay()


@shared_task
def queue_scheduled_announcements():
    now = timezone.now()
    count = 0
    for announcement in Announcement.objects.filter(queued_at__isnull=True, send_at__lte=now):
        accounts = TelegramAccount.objects.filter(
            persons__contacts__child__kindergarten=announcement.kindergarten,
            persons__contacts__receives_messages=True, is_active=True)
        if announcement.audience == Announcement.Audience.GROUP and announcement.group_id:
            today = timezone.localdate()
            accounts = accounts.filter(
                persons__contacts__child__enrollments__group_id=announcement.group_id,
                persons__contacts__child__enrollments__started_at__lte=today,
            ).filter(
                Q(persons__contacts__child__enrollments__ended_at__isnull=True) |
                Q(persons__contacts__child__enrollments__ended_at__gte=today)
            )
        elif announcement.audience == Announcement.Audience.DEBTORS:
            debtor_children = Invoice.objects.filter(
                kindergarten=announcement.kindergarten).unpaid().values_list(
                    "enrollment__child_id", flat=True)
            accounts = accounts.filter(persons__contacts__child_id__in=debtor_children)
        for account in accounts.distinct():
            enqueue(kindergarten=announcement.kindergarten, chat_id=account.chat_id,
                    kind="announcement", text=f"📢 {announcement.title}\n\n{announcement.text}",
                    dedupe_key=f"announcement:{announcement.id}:{account.chat_id}")
            count += 1
        announcement.queued_at = now
        announcement.save(update_fields=["queued_at"])
    if count:
        deliver_notification_outbox.delay()
    return count


@shared_task
def automatic_invoice_generation():
    today = timezone.localdate()
    result = {"created": 0, "skipped": 0}
    for kg in Kindergarten.objects.filter(is_active=True).select_related("policy"):
        policy = getattr(kg, "policy", None)
        if policy and today.day == policy.invoice_generation_day:
            current = generate_invoices(kg, today.replace(day=1))
            result["created"] += current["created"]
            result["skipped"] += current["skipped"]
    return result
