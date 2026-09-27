"""Servis qatlami testlari — baza bilan."""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.billing.models import Invoice, InvoiceStatus, Payment
from apps.billing.services import (add_manual_line, child_balance,
                                   generate_invoices, month_start,
                                   register_payment, reverse_payment,
                                   void_invoice, working_days_for)
from apps.school.models import (BillingPolicy, Child, Contact, Enrollment, Group,
                                Kindergarten, Tariff, WorkingCalendar)


@pytest.fixture
def kg(db):
    k = Kindergarten.objects.create(name="Test")
    BillingPolicy.objects.create(kindergarten=k)
    return k


@pytest.fixture
def setup(kg):
    t = Tariff.objects.create(kindergarten=kg, name="Standart",
                              monthly_amount=Decimal("1400000"),
                              valid_from=date(2026, 1, 1))
    g = Group.objects.create(kindergarten=kg, name="1-guruh", default_tariff=t)
    c = Child.objects.create(kindergarten=kg, full_name="Test Bola",
                             birth_date=date(2022, 1, 1))
    Contact.objects.create(
        child=c, full_name="Ota", relation="Ota-ona", phone="+998900000000",
        kind=Contact.Kind.PARENT, is_primary=True, is_payer=True)
    e = Enrollment.objects.create(child=c, group=g, tariff=t,
                                  started_at=date(2026, 1, 1))
    return {"kg": kg, "tariff": t, "group": g, "child": c, "enrollment": e}


P = date(2026, 6, 1)


def test_generation_is_idempotent(setup):
    kg = setup["kg"]
    r1 = generate_invoices(kg, P)
    r2 = generate_invoices(kg, P)
    assert r1["created"] == 1
    assert r2["created"] == 0
    assert Invoice.objects.filter(period=P).count() == 1


def test_generation_adds_mid_month_enrollment_on_second_run(setup):
    kg = setup["kg"]
    generate_invoices(kg, P)
    child = Child.objects.create(
        kindergarten=kg, full_name="Oy o'rtasidagi bola",
        birth_date=date(2022, 2, 2),
    )
    enrollment = Enrollment.objects.create(
        child=child, group=setup["group"], tariff=setup["tariff"],
        started_at=date(2026, 6, 15),
    )

    result = generate_invoices(kg, P)

    assert result["created"] == 1
    assert Invoice.objects.filter(enrollment=enrollment, period=P).exists()


def test_register_payment_rejects_non_positive_amount(setup):
    with pytest.raises(ValueError, match="0 dan katta"):
        register_payment(
            kindergarten=setup["kg"], child=setup["child"],
            amount=Decimal("-5000"), method="cash",
        )
    assert not Payment.objects.exists()


def test_tariff_change_does_not_affect_old_invoice(setup):
    kg, t = setup["kg"], setup["tariff"]
    generate_invoices(kg, P)
    old = Invoice.objects.get(period=P).total_amount

    Tariff.objects.create(kindergarten=kg, name="Yangi",
                          monthly_amount=Decimal("1900000"),
                          valid_from=date(2026, 7, 1))
    t.monthly_amount = Decimal("1900000")
    t.save()

    assert Invoice.objects.get(period=P).total_amount == old


def test_partial_payment_sets_status(setup):
    kg, child = setup["kg"], setup["child"]
    generate_invoices(kg, P)
    register_payment(kindergarten=kg, child=child, amount=Decimal("500000"),
                     method="cash", received_at=timezone.now())
    inv = Invoice.objects.get(period=P)
    assert inv.status == InvoiceStatus.PARTIAL
    assert inv.paid == Decimal("500000")


def test_full_payment_sets_paid(setup):
    kg, child = setup["kg"], setup["child"]
    generate_invoices(kg, P)
    inv = Invoice.objects.get(period=P)
    register_payment(kindergarten=kg, child=child, amount=inv.total_amount,
                     method="cash", received_at=timezone.now())
    inv.refresh_from_db()
    assert inv.status == InvoiceStatus.PAID
    assert child_balance(child) == Decimal("0")


def test_overpayment_becomes_advance_and_covers_next_month(setup):
    kg, child = setup["kg"], setup["child"]
    generate_invoices(kg, P)
    pay = register_payment(kindergarten=kg, child=child,
                           amount=Decimal("2800000"), method="cash",
                           received_at=timezone.now())
    assert pay.unallocated == Decimal("1400000")

    generate_invoices(kg, date(2026, 7, 1))
    pay.refresh_from_db()
    assert pay.unallocated == Decimal("0")
    assert Invoice.objects.get(period=date(2026, 7, 1)).status == InvoiceStatus.PAID


def test_oldest_debt_paid_first(setup):
    kg, child = setup["kg"], setup["child"]
    generate_invoices(kg, date(2026, 5, 1))
    generate_invoices(kg, date(2026, 6, 1))
    register_payment(kindergarten=kg, child=child, amount=Decimal("1400000"),
                     method="cash", received_at=timezone.now())
    may = Invoice.objects.get(period=date(2026, 5, 1))
    june = Invoice.objects.get(period=date(2026, 6, 1))
    assert may.status == InvoiceStatus.PAID
    assert june.status == InvoiceStatus.ISSUED


def test_duplicate_webhook_ignored(setup):
    kg, child = setup["kg"], setup["child"]
    generate_invoices(kg, P)
    p1 = register_payment(kindergarten=kg, child=child, amount=Decimal("100000"),
                          method="payme", external_id="TX1",
                          received_at=timezone.now())
    p2 = register_payment(kindergarten=kg, child=child, amount=Decimal("100000"),
                          method="payme", external_id="TX1",
                          received_at=timezone.now())
    assert p1.id == p2.id
    assert Payment.objects.count() == 1


def test_void_invoice_frees_payment(setup):
    kg, child = setup["kg"], setup["child"]
    generate_invoices(kg, P)
    inv = Invoice.objects.get(period=P)
    pay = register_payment(kindergarten=kg, child=child, amount=inv.total_amount,
                           method="cash", received_at=timezone.now())
    void_invoice(inv, note="xato")
    inv.refresh_from_db()
    pay.refresh_from_db()
    assert inv.status == InvoiceStatus.VOID
    assert pay.unallocated == pay.amount


def test_reverse_payment_restores_debt(setup):
    kg, child = setup["kg"], setup["child"]
    generate_invoices(kg, P)
    inv = Invoice.objects.get(period=P)
    pay = register_payment(kindergarten=kg, child=child, amount=inv.total_amount,
                           method="cash", received_at=timezone.now())
    reverse_payment(pay, note="xato o'tkazma")
    inv.refresh_from_db()
    assert inv.status == InvoiceStatus.ISSUED
    assert inv.balance == inv.total_amount


def test_manual_line_changes_total(setup):
    kg = setup["kg"]
    generate_invoices(kg, P)
    inv = Invoice.objects.get(period=P)
    before = inv.total_amount
    add_manual_line(inv, "Qo'shimcha chegirma", Decimal("-200000"))
    inv.refresh_from_db()
    assert inv.total_amount == before - Decimal("200000")


def test_holiday_calendar_affects_proration(setup):
    kg, enr = setup["kg"], setup["enrollment"]
    enr.started_at = date(2026, 6, 16)
    enr.save()

    generate_invoices(kg, P)
    without_holidays = Invoice.objects.get(period=P).total_amount

    Invoice.objects.all().delete()
    for d in [date(2026, 6, 1), date(2026, 6, 2), date(2026, 6, 3)]:
        WorkingCalendar.objects.create(kindergarten=kg, day=d, is_working=False)
    generate_invoices(kg, P)
    with_holidays = Invoice.objects.get(period=P).total_amount

    assert with_holidays > without_holidays


def test_working_days_respects_calendar(kg):
    days = working_days_for(kg, P)
    assert all(d.weekday() < 5 for d in days)
    WorkingCalendar.objects.create(kindergarten=kg, day=date(2026, 6, 6),
                                   is_working=True)
    assert date(2026, 6, 6) in working_days_for(kg, P)


def test_enrollment_ended_stops_billing(setup):
    kg, enr = setup["kg"], setup["enrollment"]
    enr.ended_at = date(2026, 5, 31)
    enr.save()
    result = generate_invoices(kg, P)
    assert result["created"] == 0


def test_audit_written_on_payment(setup):
    from apps.accounts.models import AuditLog
    kg, child = setup["kg"], setup["child"]
    generate_invoices(kg, P)
    register_payment(kindergarten=kg, child=child, amount=Decimal("100000"),
                     method="cash", received_at=timezone.now())
    assert AuditLog.objects.filter(action="payment.create").exists()
    assert AuditLog.objects.filter(action="invoice.create").exists()
