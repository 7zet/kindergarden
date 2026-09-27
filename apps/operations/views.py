from datetime import datetime
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.db import IntegrityError
from django.db.models import Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.accounts.audit import log as audit
from apps.web.access import EDIT_FINANCE, EDIT_SETTINGS, VIEW_FINANCE, require
from apps.web.views import kg_of, period_options

from .analytics import (attendance_daily, debt_dynamics, financial_snapshot,
                        group_profitability)
from .exports import management_excel, management_pdf
from .forms import (AnnouncementForm, CompensationForm, ExpenseCategoryForm,
                    ExpenseForm, PayrollEntryForm, SupplierForm)
from .models import (Announcement, CashShift, Expense, ExpenseCategory,
                     NotificationOutbox, PayrollEntry, StaffCompensation, Supplier)
from .services import (close_cash_shift, create_expense, generate_payroll,
                       open_cash_shift, shift_totals, void_expense)


def _period(request):
    raw = request.GET.get("period") or request.POST.get("period")
    try: return datetime.strptime(raw, "%Y-%m").date().replace(day=1) if raw else timezone.localdate().replace(day=1)
    except ValueError: return timezone.localdate().replace(day=1)


def _money(value):
    return Decimal(str(value or "0").replace(",", "").replace(" ", ""))


@require(VIEW_FINANCE)
def finance_dashboard(request):
    kg, period = kg_of(request), _period(request)
    snap = financial_snapshot(kg, period)
    return render(request, "operations/dashboard.html", {
        "kg": kg, "period": period, "periods": period_options(12), "snapshot": snap,
        "groups": group_profitability(kg, period),
        "debt_dynamics": debt_dynamics(kg, period_options(6)),
        "attendance_daily": attendance_daily(kg, period),
        "open_shift": CashShift.objects.filter(kindergarten=kg, status="open").first(),
        "recent_expenses": Expense.objects.filter(kindergarten=kg).select_related("category")[:8],
    })


@require(EDIT_SETTINGS)
def outbox_monitor(request):
    kg = kg_of(request)
    rows = NotificationOutbox.objects.filter(kindergarten=kg).order_by("status", "available_at")
    if request.method == "POST":
        item = get_object_or_404(rows, pk=request.POST.get("id"))
        item.status, item.attempts, item.available_at = "pending", 0, timezone.now()
        item.save(update_fields=["status", "attempts", "available_at"])
        messages.success(request, "Xabar qayta navbatga qo'yildi")
        return redirect("outbox_monitor")
    return render(request, "operations/outbox.html", {"kg": kg, "rows": rows[:250],
        "stuck": rows.filter(status="failed", attempts__gte=8).count()})


@require(VIEW_FINANCE)
def expense_list(request):
    kg, period = kg_of(request), _period(request)
    qs = Expense.objects.filter(kindergarten=kg, paid_at__year=period.year,
                                paid_at__month=period.month).select_related("category", "supplier", "group")
    total = qs.filter(is_void=False).aggregate(s=Sum("amount"))["s"] or 0
    return render(request, "operations/expenses.html", {"kg": kg, "rows": qs, "total": total,
                  "period": period, "periods": period_options(12)})


@require(EDIT_FINANCE)
def expense_new(request):
    kg = kg_of(request); form = ExpenseForm(request.POST or None, kindergarten=kg)
    if request.method == "POST" and form.is_valid():
        create_expense(kindergarten=kg, user=request.user, **form.cleaned_data)
        messages.success(request, "Xarajat saqlandi"); return redirect("expense_list")
    return render(request, "web/form.html", {"form": form, "title": "Yangi xarajat", "back": "expense_list", "kg": kg})


@require(EDIT_FINANCE)
def expense_void(request, pk):
    expense = get_object_or_404(Expense, pk=pk, kindergarten=kg_of(request))
    if request.method == "POST": void_expense(expense, user=request.user, note=request.POST.get("note", "")); messages.success(request, "Xarajat bekor qilindi")
    return redirect("expense_list")


def _simple_form(request, model, form_class, title, back):
    kg = kg_of(request); form = form_class(request.POST or None, kindergarten=kg)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False); obj.kindergarten = kg
        try:
            obj.save()
        except IntegrityError:
            form.add_error("name", "Bu nomdagi yozuv allaqachon mavjud.")
        else:
            messages.success(request, f"{title} saqlandi"); return redirect(back)
    return render(request, "web/form.html", {"form": form, "title": title, "back": back, "kg": kg})


@require(EDIT_FINANCE)
def category_new(request): return _simple_form(request, ExpenseCategory, ExpenseCategoryForm, "Xarajat kategoriyasi", "expense_list")


@require(EDIT_FINANCE)
def supplier_new(request): return _simple_form(request, Supplier, SupplierForm, "Yetkazib beruvchi", "expense_list")


@require(VIEW_FINANCE)
def cash_shifts(request):
    kg = kg_of(request)
    shifts = CashShift.objects.filter(kindergarten=kg).select_related("cashier")
    current = shifts.filter(status="open").first()
    rows = shifts[:30]
    return render(request, "operations/cash_shifts.html", {"kg": kg, "rows": rows,
                  "current": current, "totals": shift_totals(current) if current else None})


@require(EDIT_FINANCE)
def cash_shift_open(request):
    if request.method == "POST":
        try: opening = _money(request.POST.get("opening_balance", "0")); open_cash_shift(kindergarten=kg_of(request), cashier=request.user, opening_balance=opening); messages.success(request, "Kassa smenasi ochildi")
        except Exception as exc: messages.error(request, f"Smena ochilmadi: {exc}")
    return redirect("cash_shifts")


@require(EDIT_FINANCE)
def cash_shift_close(request, pk):
    shift = get_object_or_404(CashShift, pk=pk, kindergarten=kg_of(request), status="open")
    if request.method == "POST":
        try: close_cash_shift(shift, user=request.user, actual_balance=_money(request.POST["actual_balance"]), note=request.POST.get("note", "")); messages.success(request, "Kassa smenasi yopildi")
        except (InvalidOperation, KeyError): messages.error(request, "Amaldagi qoldiq noto'g'ri")
    return redirect("cash_shifts")


@require(VIEW_FINANCE)
def payroll(request):
    kg, period = kg_of(request), _period(request)
    rows = PayrollEntry.objects.filter(kindergarten=kg, period=period).select_related("employee")
    return render(request, "operations/payroll.html", {"kg": kg, "rows": rows, "period": period,
                  "periods": period_options(12), "compensations": StaffCompensation.objects.filter(user__kindergarten=kg).select_related("user")})


@require(EDIT_FINANCE)
def compensation_new(request):
    kg = kg_of(request); form = CompensationForm(request.POST or None, kindergarten=kg)
    if request.method == "POST" and form.is_valid(): form.save(); messages.success(request, "Xodim maoshi saqlandi"); return redirect("payroll")
    return render(request, "web/form.html", {"form": form, "title": "Xodim oyligi", "back": "payroll", "kg": kg})


@require(EDIT_FINANCE)
def payroll_generate(request):
    if request.method == "POST": messages.success(request, f"{generate_payroll(kg_of(request), _period(request), request.user)} ta ish haqi qatori yaratildi")
    return redirect(f"/finance/payroll/?period={_period(request):%Y-%m}")


@require(EDIT_FINANCE)
def payroll_edit(request, pk):
    item = get_object_or_404(PayrollEntry, pk=pk, kindergarten=kg_of(request)); form = PayrollEntryForm(request.POST or None, instance=item)
    if request.method == "POST" and form.is_valid(): form.save(); audit("payroll.update", item, user=request.user, after={"net": str(item.net_amount)}); messages.success(request, "Ish haqi yangilandi"); return redirect(f"/finance/payroll/?period={item.period:%Y-%m}")
    return render(request, "web/form.html", {"form": form, "title": item.employee.full_name, "back": "payroll", "kg": kg_of(request)})


@require(EDIT_SETTINGS)
def announcements(request):
    kg = kg_of(request); form = AnnouncementForm(request.POST or None, kindergarten=kg)
    if request.method == "POST" and form.is_valid():
        obj=form.save(commit=False); obj.kindergarten=kg; obj.created_by=request.user; obj.save()
        from .tasks import queue_scheduled_announcements
        queue_scheduled_announcements.delay()
        messages.success(request, "E'lon rejalashtirildi"); return redirect("announcements")
    rows = list(Announcement.objects.filter(kindergarten=kg).select_related("group")[:30])
    for item in rows:
        deliveries = NotificationOutbox.objects.filter(
            kindergarten=kg, kind="announcement",
            dedupe_key__startswith=f"announcement:{item.id}:")
        statuses = set(deliveries.values_list("status", flat=True))
        item.delivery_status = (
            "failed" if "failed" in statuses else
            "pending" if statuses & {"pending", "sending"} else
            "sent" if statuses and statuses == {"sent"} else
            "queued" if item.queued_at else
            "overdue" if item.send_at <= timezone.now() else "scheduled"
        )
    return render(request, "operations/announcements.html", {"kg": kg, "form": form,
                  "now": timezone.now(),
                  "rows": rows,
                  "outbox": NotificationOutbox.objects.filter(kindergarten=kg)[:30]})


@require(VIEW_FINANCE)
def report_excel(request):
    kg, period = kg_of(request), _period(request); response=HttpResponse(management_excel(kg, period), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"); response["Content-Disposition"]=f'attachment; filename="hisobot-{period:%Y-%m}.xlsx"'; response["Cache-Control"]="private, no-store"; return response


@require(VIEW_FINANCE)
def report_pdf(request):
    kg, period = kg_of(request), _period(request); response=HttpResponse(management_pdf(kg, period), content_type="application/pdf"); response["Content-Disposition"]=f'inline; filename="hisobot-{period:%Y-%m}.pdf"'; response["Cache-Control"]="private, no-store"; return response
