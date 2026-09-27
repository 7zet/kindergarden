import calendar
import math
from pathlib import Path
from datetime import date, datetime, timedelta
from decimal import Decimal

from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.contrib.auth.decorators import login_required
from django.contrib.auth import update_session_auth_hash
from django.contrib.sessions.models import Session
from django.db import transaction
from django.db.models import (Count, DecimalField, F, Prefetch, Q, Sum)
from django.db.models.functions import Coalesce
from django.conf import settings as dj_settings
from django.core.paginator import Paginator
from django.http import FileResponse, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from apps.accounts.audit import log as audit
from apps.accounts.models import AuditLog, Role, User
from apps.attendance.models import Attendance, CheckEvent, MonthLock, Reason, Status
from apps.attendance.services import check_in, check_out
from apps.billing.models import Invoice, InvoiceStatus, Payment
from apps.billing.services import (add_manual_line, annotate_balance,
                                   child_balance, generate_invoices,
                                   month_end, month_start, register_payment,
                                   reverse_payment, void_invoice,
                                   working_days_for)
from apps.school.models import (BillingPolicy, Child, Contact, Discount, Enrollment,
                                Group, Person, PickupPass, Tariff, ChildDocument,
                                StaffTelegramAccount, StaffTelegramLinkCode,
                                TelegramLinkCode, WorkingCalendar)

from .access import (EDIT_CHILD, EDIT_FINANCE, EDIT_GROUP, EDIT_SETTINGS,
                     MANAGE_USERS, MARK_ATTENDANCE, TAKE_PAYMENT, VIEW_CHILD,
                     VIEW_FINANCE, check_group, require, visible_children,
                     visible_groups)
from .access import CHECK_IN, CHECK_OUT, MANUAL_CHECK
from .forms import (ChildForm, ContactForm, DiscountForm, EnrollmentForm, GroupForm,
                    KindergartenDetailsForm, PaymentForm, PolicyForm, RoleForm,
                    TariffForm, UserForm, UserEditForm, AdminPasswordResetForm,
                    OwnPasswordChangeForm, TransferEnrollmentForm, ChildDocumentForm)
from .pdf_documents import (contract_pdf, debt_statement_pdf, invoice_pdf,
                            receipt_pdf)
from .ui_translation import ui_text

from apps.school.models import Application
from apps.school.services import (accept_application, end_enrollment, toggle_pause,
                                  transfer_enrollment, create_enrollment)
from .access import EDIT_APPLICATION, VIEW_APPLICATION
from .forms import AcceptForm, ApplicationForm, EndEnrollmentForm


def kg_of(request):
    """Fail closed: foydalanuvchi faqat o'z bog'chasini ko'rishi mumkin."""
    if not request.user.kindergarten_id:
        raise PermissionDenied("Foydalanuvchiga bog'cha biriktirilmagan")
    return request.user.kindergarten


def paginate(request, qs):
    page = Paginator(qs, dj_settings.PAGE_SIZE).get_page(request.GET.get("page"))
    return page


def parse_period(request):
    raw = request.GET.get("period") or request.POST.get("period")
    if raw:
        try:
            y, m = raw.split("-")[:2]
            return date(int(y), int(m), 1)
        except (ValueError, IndexError):
            pass
    return month_start(timezone.localdate())


def period_options(count=12):
    today = month_start(timezone.localdate())
    out = []
    for i in range(count):
        m = today.month - i
        y = today.year
        while m <= 0:
            m += 12
            y -= 1
        out.append(date(y, m, 1))
    return out


@require(VIEW_CHILD, MARK_ATTENDANCE)
def dashboard(request):
    kg = kg_of(request)
    if not request.user.has_perm(VIEW_FINANCE):
        return redirect("group_list")
    period = parse_period(request)
    invoices = Invoice.objects.filter(kindergarten=kg, period=period).with_balance()
    charged = invoices.aggregate(s=Sum("total_amount"))["s"] or Decimal("0")
    period_last_day = period.replace(day=calendar.monthrange(period.year, period.month)[1])
    # "Oy tushumi" barcha moliya ekranlarida aynan shu oyda real qabul qilingan
    # (storno qilinmagan) to'lovni anglatadi.
    collected = Payment.objects.filter(
        kindergarten=kg, is_reversed=False,
        received_at__date__range=(period, period_last_day),
    ).aggregate(s=Sum("amount"))["s"] or Decimal("0")
    debt_qs = Invoice.objects.filter(kindergarten=kg).unpaid()
    total_debt = sum((i.balance for i in debt_qs), Decimal("0"))
    today = timezone.localdate()
    children = Child.objects.filter(kindergarten=kg)
    open_enrollments = Enrollment.objects.filter(child__kindergarten=kg).open_on(today)
    active_enrollments = open_enrollments.filter(
        started_at__lte=today, is_paused=False)
    reserved = open_enrollments.filter(started_at__gt=today).count()
    paused = open_enrollments.filter(is_paused=True).count()
    active_count = active_enrollments.count()
    archived_count = children.filter(is_archived=True).count()

    today_marks = Attendance.objects.filter(
        enrollment__group__kindergarten=kg, day=today)
    present_today = today_marks.filter(status=Status.PRESENT).count()
    absent_today = today_marks.filter(status=Status.ABSENT).count()
    unmarked_today = max(active_count - present_today - absent_today, 0)
    inside_now = today_marks.filter(status=Status.PRESENT, arrived_at__isnull=False,
                                    left_at__isnull=True).count()
    attendance_marked = today_marks.exists()

    # Tanlangan oy bilan tugaydigan olti oylik real tushum trendi.
    trend_periods = []
    cursor = period
    for _ in range(6):
        trend_periods.append(cursor)
        cursor = (cursor - timedelta(days=1)).replace(day=1)
    trend_periods.reverse()
    revenue_trend = []
    for p in trend_periods:
        last_day = calendar.monthrange(p.year, p.month)[1]
        amount = Payment.objects.filter(
            kindergarten=kg, is_reversed=False,
            received_at__date__range=(p, p.replace(day=last_day)),
        ).aggregate(total=Sum("amount"))["total"] or Decimal("0")
        month_invoices = Invoice.objects.filter(kindergarten=kg, period=p).exclude(status="void")
        planned = month_invoices.aggregate(total=Sum("total_amount"))["total"] or Decimal("0")
        month_debt = sum((invoice.balance for invoice in month_invoices.with_balance()), Decimal("0"))
        revenue_trend.append({"period": p, "amount": amount, "planned": planned,
                              "debt": max(month_debt, Decimal("0"))})
    raw_trend_max = max((max(row["amount"], row["planned"], row["debt"])
                         for row in revenue_trend), default=Decimal("0"))
    if raw_trend_max > 0:
        rough_step = float(raw_trend_max) / 4
        magnitude = 10 ** math.floor(math.log10(rough_step))
        normalized = rough_step / magnitude
        nice_factor = next(value for value in (1, 2, 5, 10) if normalized <= value)
        trend_max = Decimal(str(nice_factor * magnitude * 4))
    else:
        trend_max = Decimal("4")
    count = max(len(revenue_trend) - 1, 1)
    for index, row in enumerate(revenue_trend):
        row["x"] = round(index * 500 / count, 1)
        row["y"] = round(136 - float(row["amount"] / trend_max * 112), 1)
        row["planned_y"] = round(136 - float(row["planned"] / trend_max * 112), 1)
        row["debt_y"] = round(136 - float(row["debt"] / trend_max * 112), 1)
    trend_points = " ".join(f'{row["x"]},{row["y"]}' for row in revenue_trend)
    planned_points = " ".join(f'{row["x"]},{row["planned_y"]}' for row in revenue_trend)
    debt_points = " ".join(f'{row["x"]},{row["debt_y"]}' for row in revenue_trend)
    trend_ticks = [trend_max * Decimal(step) / Decimal("4") for step in range(4, -1, -1)]

    groups = list(visible_groups(request.user, kg).filter(is_active=True).annotate(
        dashboard_active=Count("enrollments", distinct=True, filter=Q(
            enrollments__is_paused=False, enrollments__started_at__lte=today) & (
            Q(enrollments__ended_at__isnull=True) |
            Q(enrollments__ended_at__gte=today))),
        dashboard_reserved=Count("enrollments", distinct=True, filter=Q(
            enrollments__started_at__gt=today) & (
            Q(enrollments__ended_at__isnull=True) |
            Q(enrollments__ended_at__gte=today))),
        dashboard_present=Count("enrollments__attendance", distinct=True, filter=Q(
            enrollments__attendance__day=today,
            enrollments__attendance__status=Status.PRESENT)),
    )[:3])
    for group in groups:
        group.dashboard_occupancy = min(round(
            (group.dashboard_active + group.dashboard_reserved) / group.capacity * 100
        ), 100) if group.capacity else 0
        group.dashboard_free = max(group.capacity - group.dashboard_active - group.dashboard_reserved, 0)
        group.dashboard_debt = sum((invoice.balance for invoice in
            Invoice.objects.filter(kindergarten=kg, enrollment__group=group).unpaid()), Decimal("0"))
        group.dashboard_state = ("To'liq" if group.dashboard_occupancy >= 100 else
                                 "Deyarli to'liq" if group.dashboard_occupancy >= 85 else
                                 "Joy mavjud")

    total_children = children.filter(is_archived=False).count()
    unassigned_count = max(total_children - active_count - reserved - paused, 0)
    onboarding_steps = [
        {"label": "Bog'cha rekvizitlari", "done": bool(kg.address and kg.phone), "url": reverse("settings")},
        {"label": "Moliyaviy siyosat", "done": hasattr(kg, "policy"), "url": reverse("settings")},
        {"label": "Tarif yaratish", "done": Tariff.objects.filter(kindergarten=kg).exists(), "url": reverse("settings")},
        {"label": "Guruh yaratish", "done": Group.objects.filter(kindergarten=kg).exists(), "url": reverse("group_list")},
        {"label": "Ish kalendari", "done": WorkingCalendar.objects.filter(kindergarten=kg).exists(), "url": reverse("calendar")},
        {"label": "Birinchi bolani qo'shish", "done": total_children > 0, "url": reverse("child_new")},
        {"label": "Telegram xodim ulash", "done": StaffTelegramLinkCode.objects.filter(user__kindergarten=kg).exists(), "url": reverse("user_list")},
    ]
    onboarding_done = sum(step["done"] for step in onboarding_steps)
    ctx = {
        "kg": kg, "period": period, "periods": period_options(),
        "charged": charged, "collected": collected,
        "debt": total_debt,
        "rate": (collected / charged * 100) if charged else 0,
        "children_count": total_children,
        "active_count": active_count, "reserved_count": reserved,
        "paused_count": paused, "archived_count": archived_count,
        "unassigned_count": unassigned_count,
        "active_pct": round(active_count / total_children * 100) if total_children else 0,
        "reserved_pct": round(reserved / total_children * 100) if total_children else 0,
        "paused_pct": round(paused / total_children * 100) if total_children else 0,
        "present_today": present_today, "absent_today": absent_today,
        "unmarked_today": unmarked_today, "inside_now": inside_now,
        "attendance_marked": attendance_marked,
        "attendance_pct": round(present_today / active_count * 100) if active_count else 0,
        "revenue_trend": revenue_trend, "trend_points": trend_points,
        "planned_points": planned_points, "debt_points": debt_points,
        "trend_max": trend_max, "trend_ticks": trend_ticks,
        "groups": groups,
        "onboarding_steps": onboarding_steps, "onboarding_done": onboarding_done,
        "debtors": debt_qs.select_related("enrollment__child").order_by("period")[:8],
        "invoice_count": invoices.count(),
    }
    return render(request, "web/dashboard.html", ctx)


@login_required
def global_search(request):
    """Tenant-scoped command palette search; never exposes foreign objects."""
    kg = kg_of(request)
    query = (request.GET.get("q") or "").strip()[:80]
    results = []

    def add(kind, title, subtitle, url, icon):
        if len(results) < 24:
            results.append({"kind": kind, "title": title, "subtitle": subtitle,
                            "url": url, "icon": icon})

    actions = [
        (("yangi bola", "bola qo'shish", "янги бола", "новый ребенок", "новый ребёнок", "добавить ребенка", "добавить ребёнка"),
         "Yangi bola qo'shish", "Bolalar", reverse("child_new"), "🧒", EDIT_CHILD),
        (("invoys chiqarish", "инвойс", "счет", "счёт", "выставить счет", "выставить счёт"),
         "Invoyslarni chiqarish", "Moliya", reverse("invoice_list"), "🧾", EDIT_FINANCE),
        (("to'lov kiritish", "to'lov", "тўлов", "платеж", "платёж", "оплата", "внести платеж", "внести платёж"),
         "Yangi to'lov kiritish", "Moliya", reverse("payment_new"), "💳", TAKE_PAYMENT),
        (("kalendar", "календарь", "иш кунлари"),
         "Ish kunlari kalendari", "Sozlamalar", reverse("calendar"), "📅", EDIT_SETTINGS),
        (("davomat", "давомат", "посещаемость", "отметить посещаемость"),
         "Guruhlar davomatini ochish", "Kundalik ish", reverse("group_list"), "✅", MARK_ATTENDANCE),
        (("hisobot", "ҳисобот", "otchet", "отчет", "отчёт", "финансовый отчет", "финансовый отчёт"),
         "Moliya hisobotlari", "Hisobot", reverse("finance_dashboard"), "📊", VIEW_FINANCE),
        (("sozlamalar", "созламалар", "настройки", "система"),
         "Bog'cha sozlamalari", "Tizim", reverse("settings"), "⚙️", EDIT_SETTINGS),
    ]
    normalized_query = query.casefold().replace("ё", "е")
    seat_label = ui_text("o'rin")
    currency_label = ui_text("so'm")
    for aliases, title, subtitle, url, icon, permission in actions:
        searchable = " ".join((*aliases, title, ui_text(title), subtitle, ui_text(subtitle)))
        searchable = searchable.casefold().replace("ё", "е")
        if (not query or normalized_query in searchable) and request.user.has_perm(permission):
            add(ui_text("Amal"), ui_text(title), ui_text(subtitle), url, icon)
    if len(query) >= 2 and request.user.has_perm(VIEW_CHILD):
        for child in visible_children(request.user, kg).filter(
                Q(full_name__icontains=query) | Q(code__icontains=query))[:8]:
            add(ui_text("Bola"), child.full_name, child.code or ui_text("Bola kartasi"),
                reverse("child_detail", kwargs={"pk": child.pk}), "🧒")
        for group in visible_groups(request.user, kg).filter(name__icontains=query)[:5]:
            add(ui_text("Guruh"), group.name, f"{group.active_count}/{group.capacity} {seat_label}",
                reverse("group_detail", kwargs={"pk": group.pk}), "👥")
    if len(query) >= 2 and request.user.has_perm(VIEW_FINANCE):
        for invoice in Invoice.objects.filter(kindergarten=kg).filter(
                Q(number__icontains=query) |
                Q(enrollment__child__full_name__icontains=query)
        ).select_related("enrollment__child")[:6]:
            add(ui_text("Invoys"), invoice.number, invoice.enrollment.child.full_name,
                reverse("invoice_detail", kwargs={"pk": invoice.pk}), "🧾")
        for payment in Payment.objects.filter(kindergarten=kg).filter(
                Q(child__full_name__icontains=query) | Q(external_id__icontains=query)
        ).select_related("child")[:5]:
            add(ui_text("To'lov"), payment.child.full_name if payment.child else ui_text("Aniqlanmagan to'lov"),
                f"{payment.amount:,.0f} {currency_label}", reverse("payment_list"), "💳")
    return JsonResponse({"results": results})


@login_required
def changelog(request):
    return render(request, "web/changelog.html", {"kg": kg_of(request),
                  "app_version": dj_settings.APP_VERSION})


@require(EDIT_SETTINGS)
def system_status(request):
    from datetime import timedelta as dt_timedelta
    from apps.operations.models import NotificationOutbox, ServiceHeartbeat
    checks = {"database": True, "redis": False, "celery": False}
    try:
        import redis
        checks["redis"] = bool(redis.Redis.from_url(
            dj_settings.CELERY_BROKER_URL, socket_timeout=1,
            socket_connect_timeout=1).ping())
    except Exception:
        pass
    heartbeat = ServiceHeartbeat.objects.filter(service="celery").first()
    checks["celery"] = bool(heartbeat and heartbeat.seen_at >= timezone.now() - dt_timedelta(minutes=3))
    backup_files = sorted(Path(dj_settings.BASE_DIR, "backups").glob("*"),
                          key=lambda item: item.stat().st_mtime, reverse=True)
    failed = NotificationOutbox.objects.filter(
        kindergarten=kg_of(request), status="failed").count()
    return render(request, "web/system_status.html", {"kg": kg_of(request),
        "checks": checks, "heartbeat": heartbeat, "failed": failed,
        "latest_backup": backup_files[0] if backup_files else None,
        "app_version": dj_settings.APP_VERSION})


# ---------- Guruhlar ----------

@require(VIEW_CHILD, MARK_ATTENDANCE)
def group_list(request):
    kg = kg_of(request)
    today = timezone.localdate()
    groups = visible_groups(request.user, kg).prefetch_related("teachers").annotate(
        n_active=Count("enrollments", distinct=True, filter=Q(
            enrollments__is_paused=False,
            enrollments__started_at__lte=today) & (
            Q(enrollments__ended_at__isnull=True) |
            Q(enrollments__ended_at__gte=today))),
        n_reserved=Count("enrollments", distinct=True, filter=Q(
            enrollments__started_at__gt=today) & (
            Q(enrollments__ended_at__isnull=True) |
            Q(enrollments__ended_at__gte=today))),
        n_present=Count("enrollments__attendance", distinct=True, filter=Q(
            enrollments__attendance__day=today,
            enrollments__attendance__status="present")),
    )
    return render(request, "web/group_list.html", {"groups": groups, "kg": kg})


@require(EDIT_GROUP)
def group_form(request, pk=None):
    kg = kg_of(request)
    obj = get_object_or_404(Group, pk=pk, kindergarten=kg) if pk else None
    form = GroupForm(request.POST or None, instance=obj)
    form.fields["default_tariff"].queryset = Tariff.objects.filter(kindergarten=kg)
    staff = User.objects.filter(kindergarten=kg, is_active=True).order_by("full_name")
    form.fields["teachers"].queryset = staff
    form.fields["lead_teacher"].queryset = staff
    if request.method == "POST" and form.is_valid():
        g = form.save(commit=False)
        g.kindergarten = kg
        g.save()
        form.save_m2m()
        if g.lead_teacher_id:
            g.teachers.add(g.lead_teacher)
        messages.success(request, "Guruh saqlandi")
        return redirect("group_detail", pk=g.pk)
    return render(request, "web/form.html",
                  {"form": form, "title": "Guruh", "back": "group_list"})


@require(VIEW_CHILD, MARK_ATTENDANCE)
def group_detail(request, pk):
    kg = kg_of(request)
    group = get_object_or_404(Group, pk=pk, kindergarten=kg)
    check_group(request.user, group)
    period = parse_period(request)
    enrollments = group.enrollments.open_on().select_related("child", "tariff")
    rows = []
    for e in enrollments:
        inv = Invoice.objects.filter(enrollment=e, period=period).first()
        rows.append({"e": e, "invoice": inv,
                     "balance": inv.balance if inv else Decimal("0")})
    return render(request, "web/group_detail.html", {
        "group": group, "rows": rows, "period": period,
        "periods": period_options(), "kg": kg,
    })


@require(MARK_ATTENDANCE)
def attendance_view(request, pk):
    kg = kg_of(request)
    group = get_object_or_404(Group, pk=pk, kindergarten=kg)
    check_group(request.user, group)
    raw = request.GET.get("day")
    try:
        day = datetime.strptime(raw, "%Y-%m-%d").date() if raw else timezone.localdate()
    except ValueError:
        day = timezone.localdate()

    enrollments = list(group.enrollments.effective_on(day).select_related("child"))

    locked = MonthLock.objects.filter(
        group=group, period=month_start(day), reopened_at__isnull=True).exists()
    is_working_day = day in working_days_for(kg, month_start(day))

    if request.method == "POST":
        if not is_working_day:
            messages.error(request, "Dam olish kunida davomat belgilab bo'lmaydi. Avval Kalendar bo'limida uni ish kuni sifatida belgilang.")
            return redirect(f"{request.path}?day={day:%Y-%m-%d}")
        if locked and not request.user.has_perm(EDIT_SETTINGS):
            messages.error(request, "Bu oy yopilgan — o'zgartirib bo'lmaydi")
            return redirect(f"{request.path}?day={day:%Y-%m-%d}")
        for e in enrollments:
            value = request.POST.get(f"s_{e.id}")
            if not value:
                continue
            from apps.attendance.services import mark_daily_attendance
            try:
                mark_daily_attendance(enrollment=e, day=day, value=value,
                                      user=request.user)
            except ValidationError as exc:
                messages.error(request, f"{e.child.full_name}: {'; '.join(exc.messages)}")
        messages.success(request, f"{day:%d.%m.%Y} davomati saqlandi")
        return redirect(f"{request.path}?day={day:%Y-%m-%d}")

    marks = {a.enrollment_id: a for a in
             Attendance.objects.filter(enrollment__in=enrollments, day=day)}
    stats = {
        "present": sum(a.status == Status.PRESENT for a in marks.values()),
        "absent": sum(a.status == Status.ABSENT for a in marks.values()),
        "unmarked": len(enrollments) - len(marks),
    }
    rows = []
    for e in enrollments:
        a = marks.get(e.id)
        if a is None:
            cur = ""
        elif a.status == Status.PRESENT:
            cur = "late" if a.arrived_at else "present"
        else:
            cur = a.reason or "unexcused"
        rows.append({"e": e, "current": cur})

    return render(request, "web/attendance.html", {
        "group": group, "rows": rows, "day": day, "locked": locked,
        "is_working_day": is_working_day,
        "stats": stats,
        "prev": day - timedelta(days=1), "next": day + timedelta(days=1), "kg": kg,
    })


# ---------- Bolalar ----------

@require(VIEW_CHILD, MARK_ATTENDANCE)
def child_list(request):
    kg = kg_of(request)
    q = request.GET.get("q", "").strip()
    archived = request.GET.get("archived", "0")
    group_id = request.GET.get("group", "")
    status = request.GET.get("status", "")
    sort = request.GET.get("sort", "name")
    children = visible_children(request.user, kg)
    base_children = children
    today = timezone.localdate()
    enrollment_open = (Q(enrollments__ended_at__isnull=True) |
                       Q(enrollments__ended_at__gte=today))
    counts = {
        "active": base_children.filter(is_archived=False).filter(
            enrollment_open).distinct().count(),
        "archived": base_children.filter(is_archived=True).count(),
        "all": base_children.count(),
    }
    if status == "archive":
        children = children.filter(is_archived=True)
    elif archived == "1":
        children = children.filter(is_archived=True)
    elif archived != "all":
        children = children.filter(is_archived=False).filter(enrollment_open)
    if q:
        children = children.filter(
            Q(full_name__icontains=q) | Q(contacts__person__phone__icontains=q)).distinct()
    if group_id:
        children = children.filter(enrollments__group_id=group_id).filter(enrollment_open)
    if status == "active":
        children = children.filter(
            is_archived=False, enrollments__is_paused=False,
            enrollments__started_at__lte=today).filter(enrollment_open)
    elif status == "enrolled":
        children = children.filter(
            is_archived=False, enrollments__is_paused=False,
            enrollments__started_at__gt=today).filter(enrollment_open)
    elif status == "paused":
        children = children.filter(
            is_archived=False, enrollments__is_paused=True).filter(enrollment_open)
    orderings = {
        "name": "full_name", "-name": "-full_name",
        "age": "-birth_date", "-age": "birth_date",
        "balance": "balance", "-balance": "-balance",
    }
    children = annotate_balance(children).prefetch_related(
        Prefetch("enrollments",
                 queryset=Enrollment.objects.open_on(today)
                 .select_related("group", "tariff").order_by("started_at"),
                 to_attr="active_list"),
        Prefetch("contacts", queryset=Contact.objects.order_by(
            "-is_primary", "kind", "person__full_name").select_related("person"),
                 to_attr="contact_list"),
    ).distinct().order_by(
                     orderings.get(sort, "full_name"))
    page = paginate(request, children)
    rows = [{"c": c, "e": (c.active_list[0] if c.active_list else None),
             "parent_name": c.contact_list[0].full_name if c.contact_list else "",
             "parent_phone": c.contact_list[0].phone if c.contact_list else "",
             "balance": c.balance} for c in page]
    groups = visible_groups(request.user, kg).filter(is_active=True)
    return render(request, "web/child_list.html", {
        "rows": rows, "q": q, "page": page, "kg": kg, "groups": groups,
        "group_id": group_id, "status": status, "sort": sort,
        "archived": archived, "counts": counts,
    })


@require(EDIT_CHILD)
def child_form(request, pk=None):
    kg = kg_of(request)
    obj = get_object_or_404(Child, pk=pk, kindergarten=kg) if pk else None
    form = ChildForm(request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        c = form.save(commit=False)
        c.kindergarten = kg
        c.save()
        messages.success(request, "Bola saqlandi")
        return redirect("child_detail", pk=c.pk)
    return render(request, "web/form.html",
                  {"form": form, "title": "Bola", "back": "child_list"})


@require(VIEW_CHILD, MARK_ATTENDANCE)
def child_detail(request, pk):
    kg = kg_of(request)
    child = get_object_or_404(visible_children(request.user, kg), pk=pk)
    can_finance = request.user.has_perm(VIEW_FINANCE)
    invoices = (Invoice.objects.filter(enrollment__child=child).with_balance()
                if can_finance else Invoice.objects.none())
    payments = ((Payment.objects.filter(child=child)
                 .annotate(alloc=Coalesce(
                     Sum("allocations__amount"), Decimal("0"),
                     output_field=DecimalField(max_digits=14, decimal_places=2)))
                 .annotate(free=F("amount") - F("alloc")))
                if can_finance else Payment.objects.none())

    # Davomat: oxirgi 60 kun va joriy oy statistikasi
    since = timezone.localdate() - timedelta(days=60)
    attendance = (Attendance.objects.filter(
        enrollment__child=child, day__gte=since)
        .select_related("enrollment__group").order_by("-day"))

    period = month_start(timezone.localdate())
    month_marks = Attendance.objects.filter(
        enrollment__child=child, day__gte=period)
    att_stats = {
        "present": month_marks.filter(status=Status.PRESENT).count(),
        "sick": month_marks.filter(reason="sick").count(),
        "absent": month_marks.filter(status=Status.ABSENT).count(),
    }

    current = child.current_enrollment
    today_mark = Attendance.objects.filter(
        enrollment__child=child, day=timezone.localdate()).first()

    return render(request, "web/child_detail.html", {
        "child": child, "invoices": invoices, "payments": payments,
        "can_finance": can_finance,
        "balance": child_balance(child) if can_finance else None,
        "enrollments": child.enrollments.select_related("group", "tariff"),
        "contacts": child.contacts.all(),
        "current": current,
        "attendance": attendance[:60], "att_stats": att_stats,
        "check_events": CheckEvent.objects.filter(enrollment__child=child)
            .select_related("recorded_by", "contact", "override_by")[:60],
        "today_mark": today_mark, "period": period,
        "documents": child.documents.filter(is_archived=False),
        "kg": kg,
    })


@require(EDIT_CHILD)
def contact_form(request, child_pk, pk=None):
    kg = kg_of(request)
    child = get_object_or_404(Child, pk=child_pk, kindergarten=kg)
    obj = get_object_or_404(Contact, pk=pk, child=child) if pk else None
    form = ContactForm(request.POST or None, instance=obj, kindergarten=kg)
    form.instance.child = child
    if request.method == "POST" and form.is_valid():
        contact = form.save()
        audit("contact.save", contact, note=contact.full_name, user=request.user)
        messages.success(request, "Kontakt saqlandi")
        return redirect("child_detail", pk=child.pk)
    return render(request, "web/form.html", {
        "form": form,
        "title": "Kontakt" if obj else "Yangi kontakt",
        "back_url": reverse("child_detail", kwargs={"pk": child.pk}),
    })


@require(EDIT_CHILD)
def contact_delete(request, child_pk, pk):
    child = get_object_or_404(Child, pk=child_pk, kindergarten=kg_of(request))
    contact = get_object_or_404(Contact, pk=pk, child=child)
    if request.method == "POST":
        person = contact.person
        audit("contact.delete", contact, note=contact.full_name, user=request.user)
        contact.delete()
        if not person.contacts.exists():
            for account in person.telegram_accounts.all():
                account.persons.remove(person)
            person.is_active = False
            person.save(update_fields=["is_active"])
        messages.success(request, "Kontakt o'chirildi")
    return redirect("child_detail", pk=child.pk)


@require(EDIT_CHILD)
def child_document_upload(request, child_pk):
    kg = kg_of(request)
    child = get_object_or_404(Child, pk=child_pk, kindergarten=kg)
    form = ChildDocumentForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        document = form.save(commit=False)
        document.child, document.kindergarten, document.uploaded_by = child, kg, request.user
        document.save()
        audit("document.upload", document, note=document.title, user=request.user)
        messages.success(request, "Hujjat xavfsiz saqlandi")
        return redirect("child_detail", pk=child.pk)
    return render(request, "web/form.html", {"form": form, "multipart": True,
        "title": f"{child.full_name} — hujjat",
        "back_url": reverse("child_detail", kwargs={"pk": child.pk})})


@require(EDIT_CHILD)
def child_document_download(request, pk):
    document = get_object_or_404(ChildDocument, pk=pk, kindergarten=kg_of(request),
                                 is_archived=False)
    audit("document.download", document, note=document.title, user=request.user)
    response = FileResponse(document.file.open("rb"), as_attachment=True,
                            filename=document.file.name.rsplit("/", 1)[-1])
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response


@require(EDIT_CHILD)
def child_document_archive(request, pk):
    document = get_object_or_404(ChildDocument, pk=pk, kindergarten=kg_of(request))
    if request.method == "POST":
        document.is_archived = True
        document.save(update_fields=["is_archived"])
        audit("document.archive", document, note=document.title, user=request.user)
    return redirect("child_detail", pk=document.child_id)


@require(EDIT_SETTINGS)
def person_list(request):
    kg = kg_of(request)
    persons = Person.objects.filter(kindergarten=kg, is_active=True).prefetch_related(
        "contacts__child")
    q = (request.GET.get("q") or "").strip()
    if q:
        persons = persons.filter(Q(full_name__icontains=q) | Q(phone__icontains=q))
    return render(request, "web/person_list.html", {
        "kg": kg, "persons": persons, "q": q,
    })


@require(EDIT_SETTINGS)
@transaction.atomic
def person_merge(request, source_pk):
    kg = kg_of(request)
    source = get_object_or_404(Person.objects.select_for_update(), pk=source_pk,
                               kindergarten=kg, is_active=True)
    if request.method != "POST":
        return redirect("person_list")
    target = get_object_or_404(Person.objects.select_for_update(),
                               pk=request.POST.get("target"), kindergarten=kg,
                               is_active=True)
    if source.pk == target.pk:
        messages.error(request, "Shaxs o'ziga birlashtirilmaydi")
        return redirect("person_list")
    source_children = set(source.contacts.values_list("child_id", flat=True))
    target_children = set(target.contacts.values_list("child_id", flat=True))
    if source_children & target_children:
        messages.error(request, "Ikkala shaxs bir xil bolaga ulangan. Ruxsatlar konflikti sabab birlashtirish bloklandi.")
        return redirect("person_list")
    source.contacts.update(person=target)
    for account in source.telegram_accounts.all():
        account.persons.add(target)
        account.persons.remove(source)
    source.contact_passes.filter(used_at__isnull=True).update(used_at=timezone.now())
    source.is_active = False
    source.note = f"{target.id} shaxsiga birlashtirildi"
    source.save(update_fields=["is_active", "note"])
    audit("person.merge", target, note=f"{source.full_name} → {target.full_name}",
          before={"source": str(source.id)}, user=request.user)
    messages.success(request, f"{source.full_name} → {target.full_name} birlashtirildi")
    return redirect("person_list")


@require(EDIT_CHILD)
def enrollment_form(request, pk):
    kg = kg_of(request)
    child = get_object_or_404(Child, pk=pk, kindergarten=kg)
    form = EnrollmentForm(request.POST or None, child=child)
    form.fields["group"].queryset = Group.objects.filter(kindergarten=kg)
    form.fields["tariff"].queryset = Tariff.objects.filter(kindergarten=kg, is_active=True)
    form.fields["discount"].queryset = Discount.objects.filter(kindergarten=kg, is_active=True)
    if request.method == "POST" and form.is_valid():
        try:
            e = create_enrollment(
                child=child, group=form.cleaned_data["group"],
                tariff=form.cleaned_data["tariff"],
                discount=form.cleaned_data.get("discount"),
                started_at=form.cleaned_data["started_at"],
                ended_at=form.cleaned_data.get("ended_at"),
            )
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            audit("enrollment.create", e, user=request.user)
            messages.success(request, "Shartnoma yaratildi")
            return redirect("child_detail", pk=child.pk)
    return render(request, "web/form.html", {
        "form": form, "title": f"{child.full_name} — shartnoma", "back": "child_list"})


@require(EDIT_CHILD)
def enrollment_transfer(request, pk):
    kg = kg_of(request)
    enrollment = get_object_or_404(
        Enrollment.objects.open_on().select_related("child", "group"),
        pk=pk, child__kindergarten=kg)
    form = TransferEnrollmentForm(request.POST or None, child=enrollment.child)
    form.fields["group"].queryset = Group.objects.filter(kindergarten=kg, is_active=True)
    form.fields["tariff"].queryset = Tariff.objects.filter(kindergarten=kg, is_active=True)
    form.fields["discount"].queryset = Discount.objects.filter(kindergarten=kg, is_active=True)
    if request.method == "POST" and form.is_valid():
        try:
            new = transfer_enrollment(enrollment=enrollment,
                new_group=form.cleaned_data["group"], new_tariff=form.cleaned_data["tariff"],
                discount=form.cleaned_data.get("discount"),
                effective_date=form.cleaned_data["effective_date"])
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            audit("enrollment.transfer", new, user=request.user,
                  note=f"{enrollment.group.name} → {new.group.name}")
            messages.success(request, "Bola yangi guruhga ko'chirildi")
            return redirect("child_detail", pk=enrollment.child_id)
    return render(request, "web/form.html", {"form": form,
        "title": f"{enrollment.child.full_name} — guruhga ko'chirish",
        "back_url": reverse("child_detail", kwargs={"pk": enrollment.child_id})})


# ---------- To'lovlar ----------

@require(VIEW_FINANCE)
def invoice_list(request):
    kg = kg_of(request)
    period = parse_period(request)
    status = request.GET.get("status", "")
    qs = Invoice.objects.filter(kindergarten=kg, period=period).with_balance()
    if status:
        qs = qs.filter(status=status)
    qs = qs.select_related("enrollment__child", "enrollment__group")
    total = qs.aggregate(a=Sum("total_amount"), p=Sum("paid_amount"))
    page = paginate(request, qs)
    return render(request, "web/invoice_list.html", {
        "invoices": page, "page": page,
        "period": period, "periods": period_options(),
        "status": status, "statuses": InvoiceStatus.choices,
        "total_charged": total["a"] or 0, "total_paid": total["p"] or 0, "kg": kg,
    })


@require(EDIT_FINANCE)
def generate_invoices_view(request):
    kg = kg_of(request)
    raw_period = request.POST.get("period") if request.method == "POST" else None
    if raw_period:
        try:
            period = datetime.strptime(raw_period, "%Y-%m").date().replace(day=1)
        except ValueError:
            period = parse_period(request)
    else:
        period = parse_period(request)
    if request.method == "POST":
        result = generate_invoices(kg, period)
        messages.success(
            request,
            f"{period:%m.%Y}: {result['created']} ta invoys yaratildi, "
            f"{result['skipped']} ta allaqachon mavjud edi")
    return redirect(f"/payments/?period={period:%Y-%m}")


@require(VIEW_FINANCE)
def invoice_detail(request, pk):
    kg = kg_of(request)
    invoice = get_object_or_404(Invoice, pk=pk, kindergarten=kg)
    return render(request, "web/invoice_detail.html", {
        "invoice": invoice, "lines": invoice.lines.all(),
        "allocations": invoice.allocations.select_related("payment"), "kg": kg,
    })


def _pdf_response(content, filename):
    response = HttpResponse(content, content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="{filename}"'
    response["Cache-Control"] = "private, no-store, max-age=0"
    response["Pragma"] = "no-cache"
    response["X-Content-Type-Options"] = "nosniff"
    return response


@require(VIEW_FINANCE)
def invoice_document(request, pk):
    kg = kg_of(request)
    invoice = get_object_or_404(
        Invoice.objects.select_related("enrollment__child", "enrollment__group"),
        pk=pk, kindergarten=kg,
    )
    return _pdf_response(invoice_pdf(invoice), f"invoys-{invoice.number}.pdf")


@require(VIEW_FINANCE)
def payment_receipt(request, pk):
    kg = kg_of(request)
    payment = get_object_or_404(
        Payment.objects.select_related("child", "created_by"), pk=pk, kindergarten=kg)
    return _pdf_response(receipt_pdf(payment), f"kvitansiya-{str(payment.id)[:8]}.pdf")


@require(VIEW_FINANCE)
def enrollment_contract(request, pk):
    kg = kg_of(request)
    enrollment = get_object_or_404(
        Enrollment.objects.select_related("child", "group__kindergarten", "tariff", "discount"),
        pk=pk, child__kindergarten=kg,
    )
    return _pdf_response(contract_pdf(enrollment), f"shartnoma-{str(enrollment.id)[:8]}.pdf")


@require(VIEW_FINANCE)
def child_debt_statement(request, pk):
    kg = kg_of(request)
    child = get_object_or_404(Child, pk=pk, kindergarten=kg)
    invoices = list(
        Invoice.objects.filter(kindergarten=kg, enrollment__child=child).unpaid()
        .select_related("enrollment").order_by("period")
    )
    return _pdf_response(
        debt_statement_pdf(kg, child, invoices, timezone.localdate()),
        f"qarzdorlik-{child.code or str(child.id)[:8]}.pdf",
    )


@require(VIEW_FINANCE)
def payment_list(request):
    kg = kg_of(request)
    qs = (Payment.objects.filter(kindergarten=kg).select_related("child")
          .annotate(alloc=Coalesce(Sum("allocations__amount"), Decimal("0"),
                                   output_field=DecimalField(max_digits=14,
                                                             decimal_places=2)))
          .annotate(free=F("amount") - F("alloc")))
    page = paginate(request, qs)
    return render(request, "web/payment_list.html",
                  {"payments": page, "page": page, "kg": kg})


@require(TAKE_PAYMENT)
def payment_form(request):
    kg = kg_of(request)
    form = PaymentForm(request.POST or None)
    form.fields["child"].queryset = Child.objects.filter(kindergarten=kg, is_archived=False)
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        register_payment(
            kindergarten=kg, child=d["child"], amount=d["amount"],
            method=d["method"], received_at=d["received_at"],
            note=d["note"], user=request.user)
        messages.success(request, "To'lov qayd qilindi va taqsimlandi")
        return redirect("payment_list")
    return render(request, "web/form.html",
                  {"form": form, "title": "Yangi to'lov", "back": "payment_list"})


@require(VIEW_FINANCE)
def debt_list(request):
    kg = kg_of(request)
    today = timezone.localdate()
    qs = (Invoice.objects.filter(kindergarten=kg).unpaid()
          .select_related("enrollment__child", "enrollment__group")
          .order_by("period"))
    buckets = {"0": Decimal("0"), "30": Decimal("0"),
               "60": Decimal("0"), "90": Decimal("0")}
    total = Decimal("0")
    rows = []
    for inv in qs:
        days = (today - inv.due_at).days
        bal = inv.total_amount - inv.paid_amount
        total += bal
        key = "0" if days <= 0 else "30" if days <= 30 else "60" if days <= 60 else "90"
        buckets[key] += bal
        rows.append({"i": inv, "days": days, "bal": bal})
    page = paginate(request, rows)
    return render(request, "web/debt_list.html", {
        "rows": page, "page": page, "total": total, "buckets": buckets, "kg": kg})


# ---------- Hisobot ----------

@require(VIEW_FINANCE)
def reports(request):
    kg = kg_of(request)
    months = []
    for p in reversed(period_options(6)):
        qs = Invoice.objects.filter(kindergarten=kg, period=p).with_balance()
        charged = qs.aggregate(s=Sum("total_amount"))["s"] or Decimal("0")
        paid = qs.aggregate(s=Sum("paid_amount"))["s"] or Decimal("0")
        months.append({
            "period": p, "charged": charged, "paid": paid,
            "debt": charged - paid,
            "rate": round(paid / charged * 100, 1) if charged else 0,
        })
    groups = []
    period = parse_period(request)
    for g in Group.objects.filter(kindergarten=kg, is_active=True):
        qs = Invoice.objects.filter(
            kindergarten=kg, period=period, enrollment__group=g).with_balance()
        charged = qs.aggregate(s=Sum("total_amount"))["s"] or Decimal("0")
        paid = qs.aggregate(s=Sum("paid_amount"))["s"] or Decimal("0")
        groups.append({"g": g, "charged": charged, "paid": paid,
                       "debt": charged - paid})
    return render(request, "web/reports.html", {
        "months": months, "groups": groups, "period": period,
        "periods": period_options(), "kg": kg,
        "max_charged": max([m["charged"] for m in months] + [Decimal("1")]),
    })


# ---------- Sozlamalar ----------

@require(EDIT_SETTINGS)
def settings_view(request):
    kg = kg_of(request)
    policy, _ = BillingPolicy.objects.get_or_create(kindergarten=kg)
    section = request.POST.get("section") if request.method == "POST" else None
    form = PolicyForm(request.POST if section == "policy" else None, instance=policy)
    details_form = KindergartenDetailsForm(
        request.POST if section == "details" else None, instance=kg)
    if request.method == "POST" and section == "policy" and form.is_valid():
        form.save()
        messages.success(request, "Siyosat saqlandi")
        return redirect("settings")
    if request.method == "POST" and section == "details" and details_form.is_valid():
        details_form.save()
        audit("kindergarten.details", kg, note="Rasmiy rekvizitlar yangilandi",
              user=request.user)
        messages.success(request, "Bog'cha rekvizitlari saqlandi")
        return redirect("settings")
    return render(request, "web/settings.html", {
        "form": form, "details_form": details_form, "kg": kg,
        "tariffs": Tariff.objects.filter(kindergarten=kg),
        "discounts": Discount.objects.filter(kindergarten=kg),
    })


@require(EDIT_SETTINGS)
def tariff_form(request):
    kg = kg_of(request)
    form = TariffForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        t = form.save(commit=False)
        t.kindergarten = kg
        t.save()
        messages.success(request, "Tarif qo'shildi")
        return redirect("settings")
    return render(request, "web/form.html",
                  {"form": form, "title": "Yangi tarif", "back": "settings"})


@require(EDIT_SETTINGS)
def discount_form(request):
    kg = kg_of(request)
    form = DiscountForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        d = form.save(commit=False)
        d.kindergarten = kg
        d.save()
        messages.success(request, "Chegirma qo'shildi")
        return redirect("settings")
    return render(request, "web/form.html",
                  {"form": form, "title": "Yangi chegirma", "back": "settings"})


@require(MANAGE_USERS)
def user_list(request):
    kg = kg_of(request)
    return render(request, "web/user_list.html", {
        "users": User.objects.filter(kindergarten=kg),
        "roles": Role.objects.filter(kindergarten=kg), "kg": kg,
    })


def _managed_user(request, pk):
    target = get_object_or_404(User, pk=pk, kindergarten=kg_of(request))
    if target.is_owner and target != request.user:
        raise PermissionDenied("Egasi hisobini boshqa foydalanuvchi boshqara olmaydi.")
    return target


def _terminate_user_sessions(user):
    """Django sessionlaridan faqat berilgan foydalanuvchinikini o'chiradi."""
    count = 0
    for session in Session.objects.filter(expire_date__gte=timezone.now()):
        if str(session.get_decoded().get("_auth_user_id")) == str(user.pk):
            session.delete()
            count += 1
    return count


@require(MANAGE_USERS)
def staff_telegram_link(request, pk):
    kg = kg_of(request)
    staff = get_object_or_404(User, pk=pk, kindergarten=kg, is_active=True)
    code = StaffTelegramLinkCode.objects.create(
        user=staff, created_by=request.user,
        expires_at=timezone.now() + timedelta(minutes=15),
    )
    username = dj_settings.TELEGRAM_BOT_USERNAME.lstrip("@")
    link = f"https://t.me/{username}?start=staff_{code.token}" if username else ""
    return render(request, "web/staff_telegram_link.html", {
        "staff": staff, "link": link, "kg": kg,
    })


@require(MANAGE_USERS)
def user_form(request):
    kg = kg_of(request)
    form = UserForm(request.POST or None)
    form.fields["role"].queryset = Role.objects.filter(kindergarten=kg)
    if request.method == "POST" and form.is_valid():
        u = form.save(commit=False)
        u.kindergarten = kg
        u.set_password(form.cleaned_data["password"])
        u.must_change_password = True
        u.save()
        audit("user.create", u, user=request.user,
              after={"full_name": u.full_name, "phone": u.phone,
                     "role": str(u.role_id or ""), "is_active": u.is_active})
        messages.success(request, "Foydalanuvchi qo'shildi")
        return redirect("user_list")
    return render(request, "web/form.html",
                  {"form": form, "title": "Yangi foydalanuvchi", "back": "user_list"})


@require(MANAGE_USERS)
def user_edit(request, pk):
    target = _managed_user(request, pk)
    before = {"full_name": target.full_name, "phone": target.phone,
              "role": str(target.role_id or ""), "is_active": target.is_active}
    form = UserEditForm(request.POST or None, instance=target)
    form.fields["role"].queryset = Role.objects.filter(kindergarten=kg_of(request))
    if target.is_owner:
        form.fields.pop("role", None)
        form.fields.pop("is_active", None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        audit("user.update", user, user=request.user, before=before,
              after={"full_name": user.full_name, "phone": user.phone,
                     "role": str(user.role_id or ""), "is_active": user.is_active})
        messages.success(request, "Foydalanuvchi ma'lumotlari yangilandi")
        return redirect("user_list")
    return render(request, "web/form.html", {
        "form": form, "title": f"Foydalanuvchini tahrirlash — {target.full_name}",
        "back": "user_list",
    })


@require(MANAGE_USERS)
def user_password_reset(request, pk):
    target = _managed_user(request, pk)
    if target == request.user:
        return redirect("own_password_change")
    form = AdminPasswordResetForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        target.set_password(form.cleaned_data["password"])
        target.must_change_password = form.cleaned_data["require_change"]
        target.save(update_fields=["password", "must_change_password"])
        sessions = _terminate_user_sessions(target)
        audit("user.password_reset", target, user=request.user,
              after={"must_change_password": target.must_change_password,
                     "sessions_terminated": sessions})
        messages.success(request, "Yangi parol o'rnatildi. Eski sessiyalar tugatildi.")
        return redirect("user_list")
    return render(request, "web/password_form.html", {
        "form": form, "target": target, "title": "Parolni xavfsiz almashtirish",
        "back": "user_list",
    })


@require(MANAGE_USERS)
def user_toggle_active(request, pk):
    if request.method != "POST":
        return redirect("user_list")
    target = _managed_user(request, pk)
    if target == request.user or target.is_owner:
        raise PermissionDenied("O'z yoki egasi hisobini bloklab bo'lmaydi.")
    before = target.is_active
    target.is_active = not target.is_active
    target.save(update_fields=["is_active"])
    sessions = _terminate_user_sessions(target) if not target.is_active else 0
    audit("user.active_toggle", target, user=request.user,
          before={"is_active": before},
          after={"is_active": target.is_active, "sessions_terminated": sessions})
    messages.success(request, "Foydalanuvchi faollashtirildi" if target.is_active else "Foydalanuvchi bloklandi")
    return redirect("user_list")


@require(MANAGE_USERS)
def user_terminate_sessions(request, pk):
    if request.method != "POST":
        return redirect("user_list")
    target = _managed_user(request, pk)
    if target == request.user:
        raise PermissionDenied("Joriy sessiyani bu yerdan tugatib bo'lmaydi.")
    count = _terminate_user_sessions(target)
    audit("user.sessions_terminated", target, user=request.user,
          after={"sessions_terminated": count})
    messages.success(request, f"{count} ta faol sessiya tugatildi")
    return redirect("user_list")


@require(MANAGE_USERS)
def user_unlink_telegram(request, pk):
    if request.method != "POST":
        return redirect("user_list")
    target = _managed_user(request, pk)
    deleted, _ = StaffTelegramAccount.objects.filter(user=target).delete()
    StaffTelegramLinkCode.objects.filter(user=target, used_at__isnull=True).delete()
    audit("user.telegram_unlink", target, user=request.user,
          after={"telegram_unlinked": bool(deleted)})
    messages.success(request, "Telegram ulanishi uzildi")
    return redirect("user_list")


@login_required
def own_password_change(request):
    form = OwnPasswordChangeForm(request.user, request.POST or None)
    if request.method == "POST" and form.is_valid():
        request.user.set_password(form.cleaned_data["password"])
        request.user.must_change_password = False
        request.user.save(update_fields=["password", "must_change_password"])
        update_session_auth_hash(request, request.user)
        audit("user.password_changed", request.user, user=request.user,
              after={"must_change_password": False})
        messages.success(request, "Parolingiz muvaffaqiyatli almashtirildi")
        return redirect("dashboard")
    return render(request, "web/password_form.html", {
        "form": form, "target": request.user, "title": "Yangi parol o'rnating",
        "back": "dashboard", "forced": request.user.must_change_password,
    })


@require(MANAGE_USERS)
def role_form(request, pk=None):
    kg = kg_of(request)
    role = get_object_or_404(Role, pk=pk, kindergarten=kg) if pk else None
    before = ({"name": role.name, "permissions": list(role.permissions.values_list("id", flat=True))}
              if role else None)
    form = RoleForm(request.POST or None, instance=role)
    if request.method == "POST" and form.is_valid():
        r = form.save(commit=False)
        r.kindergarten = kg
        r.save()
        form.save_m2m()
        audit("role.update" if role else "role.create", r, user=request.user,
              before=before, after={"name": r.name,
                                    "permissions": list(r.permissions.values_list("id", flat=True))})
        messages.success(request, "Rol yangilandi" if role else "Rol yaratildi")
        return redirect("user_list")
    return render(request, "web/form.html",
                  {"form": form, "title": "Rolni tahrirlash" if role else "Yangi rol",
                   "back": "user_list"})


@require(MANAGE_USERS)
def role_delete(request, pk):
    if request.method != "POST":
        return redirect("user_list")
    role = get_object_or_404(Role, pk=pk, kindergarten=kg_of(request))
    if role.is_system or role.users.exists():
        messages.error(request, "Xodim biriktirilgan yoki tizimli rolni o'chirib bo'lmaydi")
        return redirect("user_list")
    audit("role.delete", role, user=request.user,
          before={"name": role.name,
                  "permissions": list(role.permissions.values_list("id", flat=True))})
    role.delete()
    messages.success(request, "Rol o'chirildi")
    return redirect("user_list")


# ---------- Audit ----------

@require(EDIT_SETTINGS)
def audit_list(request):
    kg = kg_of(request)
    qs = AuditLog.objects.select_related("user")
    action = request.GET.get("action", "")
    if action:
        qs = qs.filter(action=action)
    page = paginate(request, qs)
    actions = (AuditLog.objects.values_list("action", flat=True)
               .distinct().order_by("action"))
    return render(request, "web/audit_list.html", {
        "page": page, "rows": page, "actions": actions,
        "action": action, "kg": kg})


# ---------- Ish kunlari kalendari ----------

@require(EDIT_SETTINGS)
def calendar_view(request):
    kg = kg_of(request)
    period = parse_period(request)
    start, end = month_start(period), month_end(period)

    if request.method == "POST":
        chosen = set(request.POST.getlist("working"))
        WorkingCalendar.objects.filter(
            kindergarten=kg, day__range=(start, end)).delete()
        rows, d = [], start
        while d <= end:
            key = d.isoformat()
            is_working = key in chosen
            if is_working != (d.weekday() < 5):
                rows.append(WorkingCalendar(
                    kindergarten=kg, day=d, is_working=is_working,
                    note="qo'lda o'zgartirilgan"))
            d += timedelta(days=1)
        WorkingCalendar.objects.bulk_create(rows)
        audit("calendar.update", kg, note=f"{period:%m.%Y}: {len(rows)} kun")
        messages.success(request, f"{period:%B %Y} kalendari saqlandi")
        return redirect(f"/settings/calendar/?period={period:%Y-%m}")

    overrides = {c.day: c.is_working for c in WorkingCalendar.objects.filter(
        kindergarten=kg, day__range=(start, end))}
    days, d = [], start
    while d <= end:
        days.append({"d": d, "working": overrides.get(d, d.weekday() < 5),
                     "custom": d in overrides})
        d += timedelta(days=1)
    lead = start.weekday()
    return render(request, "web/calendar.html", {
        "days": days, "lead": range(lead), "period": period,
        "periods": period_options(), "kg": kg,
        "count": sum(1 for x in days if x["working"])})


# ---------- Oylik tabel va oy yopish ----------

@require(MARK_ATTENDANCE)
def tabel_view(request, pk):
    kg = kg_of(request)
    group = get_object_or_404(Group, pk=pk, kindergarten=kg)
    check_group(request.user, group)
    period = parse_period(request)
    days = working_days_for(kg, period)

    enrollments = list(group.enrollments.filter(
        Q(ended_at__isnull=True) | Q(ended_at__gte=month_start(period)),
        started_at__lte=month_end(period),
    ).select_related("child"))

    marks = {}
    for a in Attendance.objects.filter(
            enrollment__in=enrollments,
            day__range=(month_start(period), month_end(period))):
        marks[(a.enrollment_id, a.day)] = a

    # Eski yoki kalendar o'zgartirilishidan oldingi dam-kun yozuvlari
    # tabelda yashirinib qolmasin.
    exceptional_days = {day for (_, day) in marks if day not in days}
    days = sorted(set(days) | exceptional_days)

    rows = []
    for e in enrollments:
        cells, present, absent, unmarked = [], 0, 0, 0
        for d in days:
            a = marks.get((e.id, d))
            if a is None:
                code = "" if d >= e.started_at else "x"
                if code == "":
                    unmarked += 1
                cells.append({"d": d, "code": code})
            elif a.status == Status.PRESENT:
                present += 1
                cells.append({"d": d, "code": "late" if a.arrived_at else "present"})
            else:
                absent += 1
                cells.append({"d": d, "code": a.reason or "unexcused"})
        rows.append({"e": e, "cells": cells, "present": present,
                     "absent": absent, "unmarked": unmarked})

    lock = MonthLock.objects.filter(group=group, period=month_start(period)).first()
    return render(request, "web/tabel.html", {
        "group": group, "rows": rows, "days": days,
        "exceptional_days": exceptional_days, "period": period,
        "periods": period_options(), "lock": lock,
        "is_locked": bool(lock and lock.is_locked), "kg": kg})


@require(MARK_ATTENDANCE)
def month_lock(request, pk):
    kg = kg_of(request)
    group = get_object_or_404(Group, pk=pk, kindergarten=kg)
    check_group(request.user, group)
    period = month_start(parse_period(request))
    if request.method == "POST":
        lock, created = MonthLock.objects.get_or_create(
            group=group, period=period, defaults={"locked_by": request.user})
        if not created and not lock.is_locked:
            lock.reopened_at = None
            lock.locked_by = request.user
            lock.save()
        audit("attendance.lock", group, note=f"{period:%m.%Y}")
        messages.success(request, f"{period:%B %Y} yopildi")
    return redirect(f"/groups/{group.id}/tabel/?period={period:%Y-%m}")


@require(EDIT_SETTINGS)
def month_unlock(request, pk):
    kg = kg_of(request)
    group = get_object_or_404(Group, pk=pk, kindergarten=kg)
    period = month_start(parse_period(request))
    if request.method == "POST":
        lock = MonthLock.objects.filter(group=group, period=period).first()
        if lock:
            lock.reopened_at = timezone.now()
            lock.reopen_note = request.POST.get("note", "")
            lock.save()
            audit("attendance.unlock", group,
                  note=f"{period:%m.%Y}: {lock.reopen_note}")
            messages.success(request, "Oy qayta ochildi")
    return redirect(f"/groups/{group.id}/tabel/?period={period:%Y-%m}")


# ---------- Storno ----------

@require(EDIT_FINANCE)
def invoice_void(request, pk):
    kg = kg_of(request)
    invoice = get_object_or_404(Invoice, pk=pk, kindergarten=kg)
    if request.method == "POST":
        void_invoice(invoice, note=request.POST.get("note", ""), user=request.user)
        messages.success(request, "Invoys bekor qilindi")
    return redirect("invoice_detail", pk=pk)


@require(EDIT_FINANCE)
def invoice_add_line(request, pk):
    kg = kg_of(request)
    invoice = get_object_or_404(Invoice, pk=pk, kindergarten=kg)
    if request.method == "POST":
        try:
            add_manual_line(invoice, request.POST.get("title", "Tuzatish"),
                            Decimal(request.POST.get("amount", "0").replace(",", "").replace(" ", "")),
                            user=request.user)
            messages.success(request, "Qator qo'shildi")
        except Exception:
            messages.error(request, "Summa noto'g'ri")
    return redirect("invoice_detail", pk=pk)


@require(TAKE_PAYMENT)
def payment_reverse(request, pk):
    kg = kg_of(request)
    payment = get_object_or_404(Payment, pk=pk, kindergarten=kg)
    if request.method == "POST":
        reverse_payment(payment, note=request.POST.get("note", ""),
                        user=request.user)
        messages.success(request, "To'lov bekor qilindi")
    return redirect("payment_list")



# ---------- Arizalar ----------

@require(VIEW_APPLICATION, EDIT_APPLICATION)
def application_list(request):
    kg = kg_of(request)
    status = request.GET.get("status", "")
    qs = Application.objects.filter(kindergarten=kg).select_related("desired_group")
    if status == "open":
        qs = qs.filter(status__in=Application.OPEN_STATUSES)
    elif status:
        qs = qs.filter(status=status)
    counts = {s: qs.model.objects.filter(kindergarten=kg, status=s).count()
              for s, _ in Application.Status.choices}
    page = paginate(request, qs)
    return render(request, "web/application_list.html", {
        "page": page, "rows": page, "counts": counts, "status": status,
        "statuses": Application.Status.choices, "kg": kg})


@require(EDIT_APPLICATION)
def application_form(request, pk=None):
    kg = kg_of(request)
    obj = get_object_or_404(Application, pk=pk, kindergarten=kg) if pk else None
    form = ApplicationForm(request.POST or None, instance=obj)
    form.fields["desired_group"].queryset = Group.objects.filter(
        kindergarten=kg, is_active=True)
    if request.method == "POST" and form.is_valid():
        a = form.save(commit=False)
        a.kindergarten = kg
        a.save()
        audit("application.save", a, note=a.child_name)
        messages.success(request, "Ariza saqlandi")
        return redirect("application_list")
    return render(request, "web/form.html",
                  {"form": form, "title": "Ariza", "back": "application_list"})


@require(EDIT_CHILD)
def application_accept(request, pk):
    kg = kg_of(request)
    app = get_object_or_404(Application, pk=pk, kindergarten=kg)
    form = AcceptForm(request.POST or None, initial={
        "group": app.desired_group_id, "started_at": app.desired_start})
    form.fields["group"].queryset = Group.objects.filter(kindergarten=kg)
    form.fields["tariff"].queryset = Tariff.objects.filter(
        kindergarten=kg, is_active=True)
    form.fields["discount"].queryset = Discount.objects.filter(
        kindergarten=kg, is_active=True)
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        child = accept_application(
            app, group=d["group"], tariff=d["tariff"],
            started_at=d["started_at"], discount=d["discount"],
            user=request.user)
        messages.success(request, f"{child.full_name} qabul qilindi")
        return redirect("child_detail", pk=child.pk)
    return render(request, "web/form.html", {
        "form": form, "title": f"{app.child_name} — qabul qilish",
        "back": "application_list"})


# ---------- Shartnoma holati ----------

@require(EDIT_CHILD)
def enrollment_end(request, pk):
    kg = kg_of(request)
    enr = get_object_or_404(Enrollment, pk=pk, child__kindergarten=kg)
    form = EndEnrollmentForm(request.POST or None, instance=enr)
    if request.method == "POST" and form.is_valid():
        end_enrollment(enr, ended_at=form.cleaned_data["ended_at"],
                       reason=form.cleaned_data["end_reason"], user=request.user)
        messages.success(request, "Shartnoma yopildi")
        return redirect("child_detail", pk=enr.child_id)
    return render(request, "web/form.html", {
        "form": form, "title": f"{enr.child.full_name} — shartnomani yopish",
        "back": "child_list"})


@require(EDIT_CHILD)
def enrollment_pause(request, pk):
    kg = kg_of(request)
    enr = get_object_or_404(Enrollment, pk=pk, child__kindergarten=kg)
    if request.method == "POST":
        toggle_pause(enr, paused=not enr.is_paused,
                     note=request.POST.get("note", ""), user=request.user)
        messages.success(request, "To'xtatildi" if enr.is_paused else "Davom ettirildi")
    return redirect("child_detail", pk=enr.child_id)


# ---------- Kirish / chiqish nazorati ----------

@require(CHECK_IN, CHECK_OUT)
def checkdesk(request):
    kg = kg_of(request)
    today = timezone.localdate()
    query = (request.GET.get("q") or "").strip()
    groups = visible_groups(request.user, kg).filter(is_active=True)
    enrollments = list(Enrollment.objects.filter(
        group__in=groups, started_at__lte=today, is_paused=False,
    ).filter(Q(ended_at__isnull=True) | Q(ended_at__gte=today)).select_related(
        "child", "group"
    ).prefetch_related("child__contacts").order_by("group__name", "child__full_name"))
    if query:
        lowered = query.casefold()
        enrollments = [item for item in enrollments if lowered in item.child.full_name.casefold()
                       or lowered in item.group.name.casefold()]
    marks = {a.enrollment_id: a for a in Attendance.objects.filter(
        enrollment__in=enrollments, day=today
    )}
    rows = []
    for enrollment in enrollments:
        mark = marks.get(enrollment.id)
        contacts = list(enrollment.child.contacts.all())
        pickup_contacts = [contact for contact in contacts if contact.can_pickup]
        rows.append({
            "enrollment": enrollment, "mark": mark,
            "contacts": contacts, "pickup_contacts": pickup_contacts,
            "default_contact": next((c for c in contacts if c.is_primary), contacts[0] if contacts else None),
            "default_pickup": pickup_contacts[0] if pickup_contacts else None,
        })
    events = CheckEvent.objects.filter(
        enrollment__group__in=groups, occurred_at__date=today,
    ).select_related("enrollment__child", "recorded_by", "pickup_contact")[:30]
    return render(request, "web/checkdesk.html", {
        "rows": rows, "events": events, "kg": kg,
        "can_manual": request.user.has_perm(MANUAL_CHECK),
        "TELEGRAM_STAFF_APP_URL": dj_settings.TELEGRAM_STAFF_APP_URL, "q": query,
    })


@require(CHECK_IN, CHECK_OUT)
def check_action(request):
    if request.method != "POST":
        return redirect("checkdesk")
    kg = kg_of(request)
    token = request.POST.get("token", "").strip()
    enrollment_id = request.POST.get("enrollment", "").strip()
    qs = Enrollment.objects.filter(
        group__kindergarten=kg, is_paused=False, started_at__lte=timezone.localdate(),
    ).filter(Q(ended_at__isnull=True) | Q(ended_at__gte=timezone.localdate())).select_related("child", "group")
    pickup_pass = None
    if token.startswith("pickup:"):
        pickup_pass = get_object_or_404(
            PickupPass.objects.select_related("child", "contact"),
            token=token.removeprefix("pickup:")
        )
        if not pickup_pass.is_valid:
            messages.error(request, "Olib ketish QR kodi eskirgan yoki ishlatilgan")
            return redirect("checkdesk")
        enrollment = get_object_or_404(qs, child=pickup_pass.child)
        method = CheckEvent.Method.PARENT_PASS
    elif token:
        enrollment = get_object_or_404(qs, child__check_token=token)
        method = CheckEvent.Method.QR
    else:
        if not request.user.has_perm(MANUAL_CHECK):
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied("Qo'lda belgilash uchun ruxsat kerak")
        enrollment = get_object_or_404(qs, pk=enrollment_id)
        method = CheckEvent.Method.MANUAL
    check_group(request.user, enrollment.group)
    kind = CheckEvent.Kind.OUT if pickup_pass else request.POST.get("kind")
    try:
        if kind == CheckEvent.Kind.IN:
            if not request.user.has_perm(CHECK_IN):
                from django.core.exceptions import PermissionDenied
                raise PermissionDenied
            contact_id = request.POST.get("contact")
            contact = get_object_or_404(Contact, pk=contact_id, child=enrollment.child) if contact_id else None
            check_in(enrollment=enrollment, user=request.user, method=method,
                     note=request.POST.get("note", ""), contact=contact)
            messages.success(request, f"{enrollment.child.full_name} check-in qilindi")
        elif kind == CheckEvent.Kind.OUT:
            if not request.user.has_perm(CHECK_OUT):
                from django.core.exceptions import PermissionDenied
                raise PermissionDenied
            contact_id = pickup_pass.contact_id if pickup_pass else request.POST.get("pickup_contact")
            contact = get_object_or_404(
                Contact, pk=contact_id, child=enrollment.child, can_pickup=True
            ) if contact_id else None
            check_out(enrollment=enrollment, user=request.user, method=method,
                      pickup_contact=contact, note=request.POST.get("note", ""))
            if pickup_pass:
                pickup_pass.used_at = timezone.now()
                pickup_pass.save(update_fields=["used_at"])
            messages.success(request, f"{enrollment.child.full_name} check-out qilindi")
        else:
            raise ValidationError("Noma'lum amal")
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
    return redirect("checkdesk")


@require(VIEW_CHILD)
def child_qr(request, pk):
    kg = kg_of(request)
    child = get_object_or_404(visible_children(request.user, kg), pk=pk)
    import qrcode
    import qrcode.image.svg
    image = qrcode.make(
        str(child.check_token), image_factory=qrcode.image.svg.SvgPathImage,
        box_size=8, border=2,
    )
    response = HttpResponse(content_type="image/svg+xml")
    image.save(response)
    response["Content-Disposition"] = f'inline; filename="child-{child.id}.svg"'
    response["Cache-Control"] = "private, no-store"
    return response


@require(EDIT_CHILD)
def telegram_link(request, child_pk, contact_pk):
    kg = kg_of(request)
    contact = get_object_or_404(
        Contact, pk=contact_pk, child_id=child_pk, child__kindergarten=kg
    )
    code = TelegramLinkCode.objects.create(
        contact=contact, created_by=request.user,
        expires_at=timezone.now() + timedelta(minutes=15),
    )
    username = dj_settings.TELEGRAM_BOT_USERNAME.lstrip("@")
    link = f"https://t.me/{username}?start={code.token}" if username else ""
    return render(request, "web/telegram_link.html", {
        "contact": contact, "link": link, "code": code, "kg": kg,
    })
