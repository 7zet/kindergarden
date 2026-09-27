from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.accounts.audit import log as audit
from apps.billing.models import Payment

from .models import (CashShift, Expense, NotificationOutbox, PayrollEntry,
                     StaffCompensation)


def _sum(qs, field="amount"):
    return qs.aggregate(total=Sum(field))["total"] or Decimal("0")


@transaction.atomic
def create_expense(*, kindergarten, user, **data):
    expense = Expense.objects.create(kindergarten=kindergarten, created_by=user, **data)
    audit("expense.create", expense, note=expense.title,
          after={"amount": str(expense.amount), "method": expense.method}, user=user)
    return expense


@transaction.atomic
def void_expense(expense, *, user, note=""):
    if not expense.is_void:
        expense.is_void = True
        expense.note = f"{expense.note}\nBekor qilish: {note}".strip()
        expense.save(update_fields=["is_void", "note"])
        audit("expense.void", expense, note=note,
              before={"amount": str(expense.amount)}, user=user)
    return expense


@transaction.atomic
def open_cash_shift(*, kindergarten, cashier, opening_balance):
    if Decimal(opening_balance) < 0:
        raise ValueError("Boshlang'ich kassa manfiy bo'lishi mumkin emas")
    shift = CashShift.objects.create(
        kindergarten=kindergarten, cashier=cashier, opening_balance=opening_balance)
    audit("cash_shift.open", shift, after={"opening": str(opening_balance)}, user=cashier)
    return shift


def shift_totals(shift, until=None):
    end = until or shift.closed_at or timezone.now()
    income = _sum(Payment.objects.filter(
        kindergarten=shift.kindergarten, method="cash", is_reversed=False,
        received_at__gte=shift.opened_at, received_at__lte=end))
    expense = _sum(Expense.objects.filter(
        kindergarten=shift.kindergarten, method="cash", is_void=False,
        paid_at__gte=shift.opened_at, paid_at__lte=end))
    expected = shift.opening_balance + income - expense
    return {"income": income, "expense": expense, "expected": expected}


@transaction.atomic
def close_cash_shift(shift, *, user, actual_balance, note=""):
    locked = CashShift.objects.select_for_update().get(pk=shift.pk)
    if locked.status == CashShift.Status.CLOSED:
        return locked
    now = timezone.now()
    totals = shift_totals(locked, now)
    locked.closed_at = now
    locked.expected_balance = totals["expected"]
    locked.actual_balance = Decimal(actual_balance)
    if locked.actual_balance < 0:
        raise ValueError("Amaldagi kassa qoldig'i manfiy bo'lishi mumkin emas")
    locked.difference = locked.actual_balance - locked.expected_balance
    locked.status = CashShift.Status.CLOSED
    locked.close_note = note
    locked.save()
    audit("cash_shift.close", locked, note=note,
          after={"expected": str(locked.expected_balance),
                 "actual": str(locked.actual_balance),
                 "difference": str(locked.difference)}, user=user)
    return locked


@transaction.atomic
def generate_payroll(kindergarten, period, user):
    period = period.replace(day=1)
    created = 0
    for comp in StaffCompensation.objects.filter(
            user__kindergarten=kindergarten, user__is_active=True).select_related("user"):
        _, was_created = PayrollEntry.objects.get_or_create(
            kindergarten=kindergarten, employee=comp.user, period=period,
            defaults={"base_salary": comp.monthly_salary, "created_by": user})
        created += int(was_created)
    return created


def enqueue(*, kindergarten, chat_id, kind, text, dedupe_key, available_at=None):
    item, _ = NotificationOutbox.objects.get_or_create(
        dedupe_key=dedupe_key,
        defaults={"kindergarten": kindergarten, "chat_id": chat_id, "kind": kind,
                  "text": text, "available_at": available_at or timezone.now()},
    )
    return item


def enqueue_for_child(child, *, kind, text, dedupe_prefix, billing=False):
    from apps.school.models import TelegramAccount
    contacts = child.contacts.filter(
        receives_messages=True,
        **({"notify_billing": True} if billing else {"notify_attendance": True}),
    )
    person_ids = contacts.values_list("person_id", flat=True)
    accounts = TelegramAccount.objects.filter(persons__id__in=person_ids,
                                               is_active=True).distinct()
    for account in accounts:
        enqueue(kindergarten=child.kindergarten, chat_id=account.chat_id, kind=kind,
                text=text, dedupe_key=f"{dedupe_prefix}:{account.chat_id}")


def queue_invoice_notification(invoice):
    child = invoice.enrollment.child
    text = (f"🧾 {child.full_name} uchun {invoice.period:%m.%Y} davriga "
            f"{invoice.total_amount:,.0f} so'm invoys chiqarildi.\n"
            f"To'lov muddati: {invoice.due_at:%d.%m.%Y}").replace(",", " ")
    enqueue_for_child(child, kind="invoice", text=text,
                      dedupe_prefix=f"invoice:{invoice.id}", billing=True)


def queue_payment_notification(payment):
    if not payment.child_id:
        return
    text = (f"✅ {payment.child.full_name} uchun {payment.amount:,.0f} so'm to'lov "
            f"qabul qilindi.\nUsul: {payment.get_method_display()}").replace(",", " ")
    enqueue_for_child(payment.child, kind="payment", text=text,
                      dedupe_prefix=f"payment:{payment.id}", billing=True)


def queue_check_event(event):
    child = event.enrollment.child
    local = timezone.localtime(event.occurred_at)
    if event.kind == "in":
        text = (f"✅ {child.full_name} {local:%H:%M} da bog'chaga keldi.\n"
                f"Qabul qilgan: {event.recorded_by.full_name}")
    else:
        pickup = event.pickup_contact.full_name if event.pickup_contact else "ko'rsatilmagan"
        text = (f"🏠 {child.full_name} {local:%H:%M} da bog'chadan ketdi.\n"
                f"Olib ketgan: {pickup}\nTasdiqlagan: {event.recorded_by.full_name}")
    enqueue_for_child(child, kind=f"attendance_{event.kind}", text=text,
                      dedupe_prefix=f"check:{event.id}")
