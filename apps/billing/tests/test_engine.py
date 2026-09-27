from datetime import date
from decimal import Decimal

from apps.billing.engine import (Debt, Policy, allocate_payment,
                                 build_invoice_lines, invoice_total)

M = Decimal("1400000")


def wd(count=22, year=2026, month=9):
    days, d = [], 1
    while len(days) < count:
        day = date(year, month, d)
        if day.weekday() < 5:
            days.append(day)
        d += 1
    return days


def test_full_month():
    lines = build_invoice_lines(monthly_amount=M, working_days=wd(),
                                started_at=date(2026, 1, 1), present_days=22,
                                policy=Policy())
    assert invoice_total(lines) == M


def test_absence_does_not_reduce():
    lines = build_invoice_lines(monthly_amount=M, working_days=wd(),
                                started_at=date(2026, 1, 1), present_days=15,
                                policy=Policy())
    assert invoice_total(lines) == M


def test_mid_month_entry_daily():
    days = wd()
    lines = build_invoice_lines(monthly_amount=M, working_days=days,
                                started_at=days[10], present_days=12,
                                policy=Policy(rounding_step=1))
    expected = M * Decimal(12) / Decimal(22)
    assert abs(invoice_total(lines) - expected) < Decimal("0.05")


def test_half_month_mode():
    days = wd()
    lines = build_invoice_lines(monthly_amount=M, working_days=days,
                                started_at=days[15], present_days=7,
                                policy=Policy(entry_proration="half"))
    assert invoice_total(lines) == M / 2


def test_absent_month_percent():
    lines = build_invoice_lines(
        monthly_amount=M, working_days=wd(), started_at=date(2026, 1, 1),
        present_days=0,
        policy=Policy(absent_month_mode="percent",
                      absent_month_percent=Decimal("50")))
    assert invoice_total(lines) == M / 2


def test_absent_month_full_default():
    lines = build_invoice_lines(monthly_amount=M, working_days=wd(),
                                started_at=date(2026, 1, 1), present_days=0,
                                policy=Policy())
    assert invoice_total(lines) == M


def test_discount_last():
    lines = build_invoice_lines(monthly_amount=M, working_days=wd(),
                                started_at=date(2026, 1, 1), present_days=22,
                                discount_percent=Decimal("20"), policy=Policy())
    assert invoice_total(lines) == M * Decimal("0.8")


def test_outside_period():
    assert build_invoice_lines(monthly_amount=M, working_days=wd(),
                               started_at=date(2026, 12, 1), present_days=0,
                               policy=Policy()) == []


def test_allocation_oldest_first():
    debts = [Debt("b", date(2026, 8, 1), Decimal("1400000")),
             Debt("a", date(2026, 7, 1), Decimal("1400000"))]
    assert allocate_payment(Decimal("2000000"), debts) == [
        ("a", Decimal("1400000")), ("b", Decimal("600000"))]


def test_allocation_advance():
    debts = [Debt("a", date(2026, 7, 1), Decimal("1000000"))]
    result = allocate_payment(Decimal("1500000"), debts)
    assert result == [("a", Decimal("1000000"))]


def test_allocation_partial():
    debts = [Debt("a", date(2026, 7, 1), Decimal("1400000"))]
    assert allocate_payment(Decimal("800000"), debts) == [("a", Decimal("800000"))]


def test_rounding():
    days = wd()
    lines = build_invoice_lines(monthly_amount=M, working_days=days,
                                started_at=days[7], present_days=15,
                                policy=Policy(rounding_step=1000))
    assert invoice_total(lines) % 1000 == 0
