"""Bazaga tegadigan operatsiyalar. Hisob-kitob engine.py da qoladi."""

import calendar
from datetime import date, timedelta
from decimal import Decimal

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from apps.accounts.audit import log as audit

from apps.attendance.models import Attendance, Status
from apps.school.models import Enrollment, WorkingCalendar

from .engine import Debt, Policy, allocate_payment, build_invoice_lines, invoice_total
from .models import Allocation, Invoice, InvoiceLine, Payment


def month_start(d: date) -> date:
    return d.replace(day=1)


def month_end(d: date) -> date:
    return d.replace(day=calendar.monthrange(d.year, d.month)[1])


def working_days_for(kindergarten, period: date) -> list:
    """Kalendarda yozuv bo'lsa — o'sha, bo'lmasa dushanba-juma."""
    start, end = month_start(period), month_end(period)
    overrides = {
        c.day: c.is_working
        for c in WorkingCalendar.objects.filter(
            kindergarten=kindergarten, day__range=(start, end)
        )
    }
    days, d = [], start
    while d <= end:
        working = overrides.get(d, d.weekday() < 5)
        if working:
            days.append(d)
        d += timedelta(days=1)
    return days


def policy_of(kindergarten) -> Policy:
    p = kindergarten.policy
    return Policy(
        entry_proration=p.entry_proration,
        exit_proration=p.exit_proration,
        absent_month_mode=p.absent_month_mode,
        absent_month_percent=p.absent_month_percent,
        absent_month_threshold=p.absent_month_threshold,
        rounding_step=p.rounding_step,
    )


def _next_number(kindergarten, period) -> str:
    count = Invoice.objects.filter(kindergarten=kindergarten, period=period).count()
    tenant = str(kindergarten.pk).replace("-", "")[:8].upper()
    return f"INV-{tenant}-{period:%Y%m}-{count + 1:04d}"


@transaction.atomic
def generate_invoices(kindergarten, period: date) -> dict:
    """Bir oy uchun invoyslarni chiqaradi. Idempotent — ikki marta
    chaqirsa ham dublikat yaratmaydi."""
    period = month_start(period)
    start, end = period, month_end(period)
    policy = policy_of(kindergarten)
    working = working_days_for(kindergarten, period)
    pol = kindergarten.policy

    created, skipped = 0, 0
    enrollments = (
        Enrollment.objects
        .filter(group__kindergarten=kindergarten, started_at__lte=end)
        .filter(models_q(end)).exclude(is_paused=True)
        .select_related("child", "tariff", "discount")
    )

    for enr in enrollments:
        if Invoice.objects.filter(enrollment=enr, period=period).exists():
            skipped += 1
            continue

        present = Attendance.objects.filter(
            enrollment=enr, day__range=(start, end), status=Status.PRESENT
        ).count()

        lines = build_invoice_lines(
            monthly_amount=enr.tariff.monthly_amount,
            working_days=working,
            started_at=enr.started_at,
            ended_at=enr.ended_at,
            present_days=present,
            discount_percent=enr.discount.percent if enr.discount else Decimal("0"),
            discount_name=enr.discount.name if enr.discount else "",
            policy=policy,
        )
        if not lines:
            continue

        due_day = min(pol.due_day, calendar.monthrange(period.year, period.month)[1])
        invoice = Invoice.objects.create(
            kindergarten=kindergarten,
            enrollment=enr,
            number=_next_number(kindergarten, period),
            period=period,
            issued_at=timezone.localdate(),
            due_at=period.replace(day=due_day),
            total_amount=invoice_total(lines),
        )
        InvoiceLine.objects.bulk_create([
            InvoiceLine(invoice=invoice, kind=l.kind, title=l.title,
                        amount=l.amount, meta=l.meta)
            for l in lines
        ])
        audit("invoice.create", invoice,
              note=f"{enr.child.full_name} — {period:%m.%Y}",
              after={"total": str(invoice.total_amount)})
        from apps.operations.services import queue_invoice_notification
        queue_invoice_notification(invoice)
        created += 1

    # Avanslarni yangi invoyslarga yoyish
    for payment in Payment.objects.filter(
        kindergarten=kindergarten, is_reversed=False, child__isnull=False
    ).select_related("child"):
        if payment.unallocated > 0:
            _spread(payment)

    return {"created": created, "skipped": skipped}


def models_q(end):
    from django.db.models import Q
    return Q(ended_at__isnull=True) | Q(ended_at__gte=end.replace(day=1))


def _spread(payment: Payment) -> None:
    """To'lovning taqsimlanmagan qismini ochiq invoyslarga yoyadi."""
    remaining = payment.unallocated
    if remaining <= 0:
        return
    invoices = list(
        Invoice.objects.filter(enrollment__child=payment.child).unpaid().order_by("period")
    )
    debts = [Debt(i.id, i.period, i.balance) for i in invoices]
    for invoice_id, part in allocate_payment(remaining, debts):
        Allocation.objects.create(payment=payment, invoice_id=invoice_id, amount=part)
    for inv in Invoice.objects.filter(id__in=[i.id for i in invoices]):
        inv.refresh_status()


@transaction.atomic
def register_payment(*, kindergarten, child, amount, method, received_at=None,
                     external_id="", note="", user=None) -> Payment:
    """To'lovni qayd qiladi va eng eski qarzdan boshlab taqsimlaydi.
    Takroriy webhook uchun external_id bo'yicha idempotent."""
    amount = Decimal(amount)
    if amount <= 0:
        raise ValueError("To'lov summasi 0 dan katta bo'lishi kerak")

    if external_id:
        existing = Payment.objects.filter(kindergarten=kindergarten, method=method,
                                          external_id=external_id).first()
        if existing:
            return existing

    payment = Payment.objects.create(
        kindergarten=kindergarten,
        child=child,
        method=method,
        external_id=external_id,
        amount=amount,
        received_at=received_at or timezone.now(),
        note=note,
        created_by=user,
    )
    audit("payment.create", payment,
          note=f"{child.full_name if child else '—'} — {payment.get_method_display()}",
          after={"amount": str(payment.amount)})
    _spread(payment)
    from apps.operations.services import queue_payment_notification
    queue_payment_notification(payment)
    return payment


def child_balance(child) -> Decimal:
    """Bitta bola uchun qoldiq. Ro'yxatlarda ishlatmang — N+1 beradi,
    o'rniga annotate_balance() dan foydalaning."""
    from django.db.models import Sum
    charged = (Invoice.objects.filter(enrollment__child=child)
               .exclude(status="void")
               .aggregate(s=Sum("total_amount"))["s"] or Decimal("0"))
    paid = (Payment.objects.filter(child=child, is_reversed=False)
            .aggregate(s=Sum("amount"))["s"] or Decimal("0"))
    return charged - paid


def annotate_balance(child_qs):
    """Bolalar ro'yxatiga qoldiqni bitta so'rovda qo'shadi.

    Ikkita alohida subquery ishlatiladi — JOIN qilinsa qatorlar
    ko'payib, summalar bir necha marta qo'shilib ketadi."""
    from django.db.models import OuterRef, Subquery, Sum
    from django.db.models.functions import Coalesce

    charged = (
        Invoice.objects.filter(enrollment__child=OuterRef("pk"))
        .exclude(status="void")
        .values("enrollment__child")
        .annotate(s=Sum("total_amount"))
        .values("s")
    )
    paid = (
        Payment.objects.filter(child=OuterRef("pk"), is_reversed=False)
        .values("child")
        .annotate(s=Sum("amount"))
        .values("s")
    )
    zero = Decimal("0")
    dec = models_decimal()
    return child_qs.annotate(
        charged=Coalesce(Subquery(charged, output_field=dec), zero),
        paid=Coalesce(Subquery(paid, output_field=dec), zero),
    ).annotate(balance=F("charged") - F("paid"))


def models_decimal():
    from django.db.models import DecimalField
    return DecimalField(max_digits=14, decimal_places=2)


@transaction.atomic
def void_invoice(invoice, note="", user=None):
    """Invoysni bekor qiladi. O'chirmaydi — holatini VOID qiladi va
    taqsimlangan to'lovlarni bo'shatadi."""
    from .models import InvoiceStatus
    before = {"status": invoice.status, "total": str(invoice.total_amount)}

    # Avval VOID qilamiz — aks holda bo'shatilgan to'lov shu invoysga
    # qayta yopishib qoladi (unpaid() VOID'ni chiqarib tashlaydi).
    invoice.status = InvoiceStatus.VOID
    invoice.save(update_fields=["status"])

    payments = [a.payment for a in invoice.allocations.select_related("payment")]
    invoice.allocations.all().delete()
    for pay in payments:
        _spread(pay)
    audit("invoice.void", invoice, note=note, before=before,
          after={"status": invoice.status}, user=user)
    return invoice


@transaction.atomic
def reverse_payment(payment, note="", user=None):
    """To'lovni bekor qiladi. Taqsimotlar o'chadi, invoyslar holati qayta
    hisoblanadi. To'lov yozuvi qoladi — tarix buzilmaydi."""
    invoice_ids = list(payment.allocations.values_list("invoice_id", flat=True))
    payment.allocations.all().delete()
    payment.is_reversed = True
    payment.save(update_fields=["is_reversed"])
    for inv in Invoice.objects.filter(id__in=invoice_ids):
        inv.refresh_status()
    audit("payment.reverse", payment, note=note,
          before={"amount": str(payment.amount)}, user=user)
    return payment


@transaction.atomic
def add_manual_line(invoice, title, amount, user=None):
    """Invoysga qo'lda tuzatish qatori qo'shadi."""
    from .models import LineKind
    line = InvoiceLine.objects.create(
        invoice=invoice, kind=LineKind.MANUAL, title=title, amount=Decimal(amount))
    invoice.recalc_total()
    invoice.refresh_status()
    audit("invoice.manual_line", invoice, note=f"{title}: {amount}", user=user)
    return line
