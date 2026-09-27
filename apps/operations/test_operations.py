from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.billing.models import Invoice, InvoiceLine, LineKind
from apps.billing.services import register_payment
from apps.school.models import BillingPolicy, Child, Enrollment, Group, Kindergarten, Tariff

from .exports import management_excel, management_pdf
from .models import (Announcement, CashShift, Expense, ExpenseCategory, NotificationOutbox,
                     StaffCompensation)
from .services import (close_cash_shift, create_expense, generate_payroll,
                       open_cash_shift, shift_totals)
from .tasks import deliver_notification_outbox


@pytest.fixture
def operation_setup(db, client):
    kg = Kindergarten.objects.create(name="Test bog'cha")
    BillingPolicy.objects.create(kindergarten=kg)
    owner = User.objects.create_user(phone="+998901010101", password="test-pass",
                                     full_name="Egasi", kindergarten=kg, is_owner=True)
    tariff = Tariff.objects.create(kindergarten=kg, name="Standart",
                                   monthly_amount=Decimal("1000000"), valid_from=date(2026, 1, 1))
    group = Group.objects.create(kindergarten=kg, name="Guruh", default_tariff=tariff)
    child = Child.objects.create(kindergarten=kg, full_name="Bola", birth_date=date(2022, 1, 1))
    enr = Enrollment.objects.create(child=child, group=group, tariff=tariff, started_at=date(2026, 8, 1))
    inv = Invoice.objects.create(kindergarten=kg, enrollment=enr, number="INV-T-1",
                                 period=date(2026, 8, 1), issued_at=date(2026, 8, 1),
                                 due_at=date(2026, 8, 10), total_amount=Decimal("1000000"))
    InvoiceLine.objects.create(invoice=inv, kind=LineKind.TUITION, title="Oylik",
                               amount=Decimal("1000000"))
    category = ExpenseCategory.objects.get(kindergarten=kg, name="Oziq-ovqat")
    client.force_login(owner)
    return client, kg, owner, child, group, category


def test_cash_shift_and_expense_are_reconciled(operation_setup):
    client, kg, owner, child, group, category = operation_setup
    shift = open_cash_shift(kindergarten=kg, cashier=owner, opening_balance=Decimal("100000"))
    register_payment(kindergarten=kg, child=child, amount=Decimal("500000"), method="cash", user=owner)
    create_expense(kindergarten=kg, user=owner, category=category, supplier=None, group=group,
                   title="Mahsulot", amount=Decimal("120000"), method="cash",
                   paid_at=timezone.now(), document_number="", note="")
    totals = shift_totals(shift)
    assert totals == {"income": Decimal("500000"), "expense": Decimal("120000"),
                      "expected": Decimal("480000")}
    closed = close_cash_shift(shift, user=owner, actual_balance=Decimal("479000"))
    assert closed.difference == Decimal("-1000") and closed.status == CashShift.Status.CLOSED


def test_payroll_and_management_exports(operation_setup):
    client, kg, owner, child, group, category = operation_setup
    StaffCompensation.objects.create(user=owner, monthly_salary=Decimal("3000000"),
                                     effective_from=date(2026, 1, 1))
    assert generate_payroll(kg, date(2026, 8, 1), owner) == 1
    assert management_excel(kg, date(2026, 8, 1)).startswith(b"PK")
    assert management_pdf(kg, date(2026, 8, 1)).startswith(b"%PDF")
    assert client.get(reverse("management_report_excel") + "?period=2026-08").status_code == 200


def test_notification_outbox_retries_and_succeeds(operation_setup):
    client, kg, owner, child, group, category = operation_setup
    item = NotificationOutbox.objects.create(
        kindergarten=kg, chat_id=123, kind="test", text="Salom",
        dedupe_key="test:123", available_at=timezone.now())
    with patch("apps.operations.tasks.send_message", return_value={"ok": True}):
        result = deliver_notification_outbox()
    item.refresh_from_db()
    assert result["sent"] == 1 and item.status == NotificationOutbox.Status.SENT


def test_other_kindergarten_cannot_see_finance(operation_setup):
    client, kg, owner, child, group, category = operation_setup
    other = Kindergarten.objects.create(name="Boshqa")
    BillingPolicy.objects.create(kindergarten=other)
    outsider = User.objects.create_user(phone="+998902020202", password="test-pass",
                                        full_name="Boshqa", kindergarten=other, is_owner=True)
    expense = create_expense(kindergarten=kg, user=owner, category=category, supplier=None,
                             group=None, title="Yashirin", amount=10, method="cash",
                             paid_at=timezone.now(), document_number="", note="")
    client.force_login(outsider)
    response = client.post(reverse("expense_void", args=[expense.pk]), {"note": "x"})
    assert response.status_code == 404


def test_expense_form_accepts_grouped_money(operation_setup):
    client, kg, _, _, group, category = operation_setup
    response = client.post(reverse("expense_new"), {
        "category": category.pk, "supplier": "", "group": group.pk,
        "title": "Formatlangan summa", "amount": "1,000,000.50",
        "method": "cash", "paid_at": "2026-08-31T10:30",
        "document_number": "", "note": "",
    })
    assert response.status_code == 302
    assert Expense.objects.get(title="Formatlangan summa").amount == Decimal("1000000.50")


def test_duplicate_expense_category_is_form_error_not_500(operation_setup):
    client, kg, *_ = operation_setup
    before = ExpenseCategory.objects.filter(kindergarten=kg, name="Oziq-ovqat").count()
    response = client.post(reverse("expense_category_new"), {
        "name": "oziq-ovqat", "kind": "food", "is_active": "on",
    })
    assert response.status_code == 200
    assert "allaqachon mavjud" in response.content.decode()
    assert ExpenseCategory.objects.filter(kindergarten=kg, name__iexact="oziq-ovqat").count() == before


@patch("apps.operations.tasks.queue_scheduled_announcements.delay")
def test_announcement_requires_and_saves_audience_group(delay, operation_setup):
    client, kg, *_rest, group, _category = operation_setup
    response = client.post(reverse("announcements"), {
        "title": "Guruh e'loni", "text": "Faqat shu guruh uchun",
        "audience": "group", "group": group.pk,
        "send_at": "2026-09-30T10:00",
    })
    assert response.status_code == 302
    item = Announcement.objects.get(title="Guruh e'loni")
    assert item.audience == Announcement.Audience.GROUP
    assert item.group == group
    delay.assert_called_once()


@pytest.mark.parametrize("route", ["finance_dashboard", "expense_list", "cash_shifts",
                                    "payroll", "announcements"])
def test_operation_pages_render(operation_setup, route):
    client, *_ = operation_setup
    assert client.get(reverse(route)).status_code == 200
