import calendar
from datetime import date
from decimal import Decimal

from django.db.models import Count, DecimalField, F, Q, Sum
from django.db.models.functions import Coalesce

from apps.attendance.models import Attendance, CheckEvent, Status
from apps.billing.models import Allocation, Invoice, Payment
from apps.school.models import Group

from .models import Expense, PayrollEntry


DECIMAL = DecimalField(max_digits=16, decimal_places=2)


def bounds(period):
    start = period.replace(day=1)
    end = period.replace(day=calendar.monthrange(period.year, period.month)[1])
    return start, end


def financial_snapshot(kg, period):
    start, end = bounds(period)
    invoices = Invoice.objects.filter(kindergarten=kg, period=start).exclude(status="void")
    charged = invoices.aggregate(s=Sum("total_amount"))["s"] or Decimal("0")
    payments = Payment.objects.filter(kindergarten=kg, is_reversed=False,
                                      received_at__date__range=(start, end))
    income = payments.aggregate(s=Sum("amount"))["s"] or Decimal("0")
    expenses = Expense.objects.filter(kindergarten=kg, is_void=False,
                                      paid_at__date__range=(start, end))
    expense_total = expenses.aggregate(s=Sum("amount"))["s"] or Decimal("0")
    payroll = PayrollEntry.objects.filter(kindergarten=kg, period=start,
                                          status=PayrollEntry.Status.PAID)
    payroll_total = sum((p.net_amount for p in payroll), Decimal("0"))
    operating_cost = expense_total + payroll_total
    methods = list(payments.values("method").annotate(total=Sum("amount"), count=Count("id"))
                   .order_by("method"))
    expense_kinds = list(expenses.values("category__kind", "category__name")
                         .annotate(total=Sum("amount")).order_by("category__kind"))
    present = Attendance.objects.filter(enrollment__group__kindergarten=kg,
                                        day__range=(start, end), status=Status.PRESENT).count()
    checkins = CheckEvent.objects.filter(enrollment__group__kindergarten=kg,
                                         occurred_at__date__range=(start, end), kind="in").count()
    checkouts = CheckEvent.objects.filter(enrollment__group__kindergarten=kg,
                                          occurred_at__date__range=(start, end), kind="out").count()
    return {"period": start, "start": start, "end": end, "charged": charged,
            "income": income, "expenses": expense_total, "payroll": payroll_total,
            "operating_cost": operating_cost, "profit": income - operating_cost,
            "plan_rate": income / charged * 100 if charged else Decimal("0"),
            "methods": methods, "expense_kinds": expense_kinds,
            "present": present, "checkins": checkins, "checkouts": checkouts}


def debt_dynamics(kg, months):
    result = []
    for period in months:
        _, end = bounds(period)
        charged = Invoice.objects.filter(
            kindergarten=kg, period__lte=period).exclude(status="void").aggregate(
                s=Sum("total_amount"))["s"] or Decimal("0")
        paid = Payment.objects.filter(
            kindergarten=kg, is_reversed=False, received_at__date__lte=end).aggregate(
                s=Sum("amount"))["s"] or Decimal("0")
        result.append({"period": period, "debt": max(charged - paid, Decimal("0"))})
    return result


def group_profitability(kg, period):
    start, end = bounds(period)
    rows = []
    for group in Group.objects.filter(kindergarten=kg, is_active=True):
        charged = Invoice.objects.filter(kindergarten=kg, period=start,
                                         enrollment__group=group).exclude(status="void").aggregate(
                                             s=Sum("total_amount"))["s"] or Decimal("0")
        collected = Allocation.objects.filter(
            invoice__kindergarten=kg, invoice__enrollment__group=group,
            payment__is_reversed=False, payment__received_at__date__range=(start, end)).aggregate(
                s=Sum("amount"))["s"] or Decimal("0")
        direct = Expense.objects.filter(kindergarten=kg, group=group, is_void=False,
                                        paid_at__date__range=(start, end)).aggregate(
                                            s=Sum("amount"))["s"] or Decimal("0")
        rows.append({"group": group, "charged": charged, "collected": collected,
                     "direct_cost": direct, "margin": collected - direct})
    return rows


def attendance_daily(kg, period):
    start, end = bounds(period)
    marks = {row["day"]: row for row in Attendance.objects.filter(
        enrollment__group__kindergarten=kg, day__range=(start, end)).values("day").annotate(
            present=Count("id", filter=Q(status=Status.PRESENT)),
            absent=Count("id", filter=Q(status="absent")))}
    events = CheckEvent.objects.filter(enrollment__group__kindergarten=kg,
                                       occurred_at__date__range=(start, end)).values(
                                           "occurred_at__date").annotate(
        checkins=Count("id", filter=Q(kind="in")),
        checkouts=Count("id", filter=Q(kind="out")))
    for row in events:
        day = row["occurred_at__date"]
        marks.setdefault(day, {"day": day, "present": 0, "absent": 0}).update(row)
    return sorted([{"day": day, "present": row.get("present", 0),
                    "absent": row.get("absent", 0), "checkins": row.get("checkins", 0),
                    "checkouts": row.get("checkouts", 0)} for day, row in marks.items()],
                  key=lambda x: x["day"])
