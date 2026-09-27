"""Billing yadrosi — Django'ni import qilmaydi, bazaga tegmaydi.

Barcha pul hisob-kitobi shu yerda. Boshqa hech qaerda summa
hisoblanmaydi: na view'da, na template'da, na JS'da.
"""

from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_HALF_UP, Decimal


@dataclass(frozen=True)
class Line:
    kind: str
    title: str
    amount: Decimal
    meta: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Policy:
    entry_proration: str = "daily"
    exit_proration: str = "daily"
    absent_month_mode: str = "full"
    absent_month_percent: Decimal = Decimal("100")
    absent_month_threshold: int = 0
    rounding_step: int = 100


def round_money(value: Decimal, step: int) -> Decimal:
    if step <= 1:
        return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    q = Decimal(step)
    return (value / q).quantize(Decimal("1"), rounding=ROUND_HALF_UP) * q


def covered_working_days(working_days, started_at, ended_at):
    return [
        d for d in working_days
        if d >= started_at and (ended_at is None or d <= ended_at)
    ]


def _factor(mode: str, covered: int, total: int) -> Decimal:
    if total == 0:
        return Decimal("0")
    if mode == "full":
        return Decimal("1")
    if mode == "half":
        return Decimal("1") if covered * 2 > total else Decimal("0.5")
    return Decimal(covered) / Decimal(total)


def build_invoice_lines(
    *,
    monthly_amount: Decimal,
    working_days: list,
    started_at: date,
    ended_at=None,
    present_days: int = 0,
    discount_percent: Decimal = Decimal("0"),
    discount_name: str = "",
    policy: Policy,
) -> list:
    """Bir oy uchun invoys qatorlari.

    present_days faqat 'butun oy kelmadi' holatini aniqlash uchun.
    Ovqat puli yo'q, shuning uchun oddiy kelmagan kun summaga ta'sir qilmaydi.
    """
    total_days = len(working_days)
    covered = covered_working_days(working_days, started_at, ended_at)
    covered_count = len(covered)
    if covered_count == 0:
        return []

    lines = [Line("tuition", "Oylik to'lov", monthly_amount, {"days": total_days})]

    if covered_count < total_days:
        mode = (
            policy.entry_proration
            if started_at > working_days[0]
            else policy.exit_proration
        )
        adjustment = monthly_amount * _factor(mode, covered_count, total_days) - monthly_amount
        if adjustment != 0:
            lines.append(Line(
                "proration",
                f"Qisman oy ({covered_count}/{total_days} kun)",
                adjustment,
                {"covered": covered_count, "total": total_days, "mode": mode},
            ))
    elif present_days <= policy.absent_month_threshold:
        base = monthly_amount
        if policy.absent_month_mode == "none":
            lines.append(Line("hold", "Oy davomida kelmadi", -base))
        elif policy.absent_month_mode == "percent":
            keep = base * policy.absent_month_percent / Decimal("100")
            lines.append(Line(
                "hold",
                f"Joy saqlash ({policy.absent_month_percent}%)",
                keep - base,
                {"present_days": present_days},
            ))

    if discount_percent > 0:
        subtotal = sum(l.amount for l in lines)
        cut = subtotal * discount_percent / Decimal("100")
        lines.append(Line(
            "discount",
            discount_name or f"Chegirma {discount_percent}%",
            -cut,
            {"percent": str(discount_percent)},
        ))

    return [
        Line(l.kind, l.title, round_money(l.amount, policy.rounding_step), l.meta)
        for l in lines
    ]


def invoice_total(lines) -> Decimal:
    return sum((l.amount for l in lines), Decimal("0"))


@dataclass
class Debt:
    invoice_id: object
    period: date
    balance: Decimal


def allocate_payment(amount: Decimal, debts: list) -> list:
    """Eng eski qarzdan boshlab yopadi. Bu qattiq qoida, sozlama emas.
    Qolgan summa — avans."""
    remaining = amount
    result = []
    for debt in sorted(debts, key=lambda d: d.period):
        if remaining <= 0:
            break
        if debt.balance <= 0:
            continue
        take = min(remaining, debt.balance)
        result.append((debt.invoice_id, take))
        remaining -= take
    return result
