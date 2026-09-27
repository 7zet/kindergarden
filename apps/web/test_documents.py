from datetime import date
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.billing.models import Allocation, Invoice, InvoiceLine, LineKind, Payment
from apps.school.models import (BillingPolicy, Child, Contact, Enrollment, Group,
                                Kindergarten, Tariff)


@pytest.fixture
def documents(db, client):
    kg = Kindergarten.objects.create(
        name="Mehribon bog'cha", legal_name="MEHRIBON NMTT MCHJ",
        address="Toshkent shahri", phone="+998901234567", inn="123456789",
        bank_name="Test bank", bank_account="20208000123456789001",
        bank_mfo="00001", director_name="Aliyeva Dilnoza",
    )
    BillingPolicy.objects.create(kindergarten=kg)
    owner = User.objects.create_user(
        phone="+998900000001", password="strong-pass", full_name="Egasi",
        kindergarten=kg, is_owner=True,
    )
    tariff = Tariff.objects.create(
        kindergarten=kg, name="Standart", monthly_amount=Decimal("1200000"),
        valid_from=date(2026, 1, 1),
    )
    group = Group.objects.create(kindergarten=kg, name="Quyoshcha", default_tariff=tariff)
    child = Child.objects.create(
        kindergarten=kg, full_name="G'aniyeva Maftuna", birth_date=date(2022, 5, 2))
    Contact.objects.create(
        child=child, full_name="G'aniyeva Madina", relation="Onasi",
        phone="+998901112233", kind=Contact.Kind.PARENT, is_payer=True,
    )
    enrollment = Enrollment.objects.create(
        child=child, group=group, tariff=tariff, started_at=date(2026, 8, 1))
    invoice = Invoice.objects.create(
        kindergarten=kg, enrollment=enrollment, number="INV-2026-0001",
        period=date(2026, 8, 1), issued_at=date(2026, 8, 1),
        due_at=date(2026, 8, 10), total_amount=Decimal("1200000"),
    )
    InvoiceLine.objects.create(
        invoice=invoice, kind=LineKind.TUITION, title="Oylik to'lov",
        amount=Decimal("1200000"))
    payment = Payment.objects.create(
        kindergarten=kg, child=child, method="cash", amount=Decimal("500000"),
        received_at=timezone.now(), created_by=owner,
    )
    Allocation.objects.create(payment=payment, invoice=invoice, amount=Decimal("500000"))
    client.force_login(owner)
    return client, kg, child, enrollment, invoice, payment


@pytest.mark.parametrize("route,item", [
    ("invoice_pdf", "invoice"),
    ("payment_receipt", "payment"),
    ("enrollment_contract", "enrollment"),
    ("child_debt_statement", "child"),
])
def test_document_is_private_valid_pdf(documents, route, item):
    client, kg, child, enrollment, invoice, payment = documents
    objects = {"child": child, "enrollment": enrollment,
               "invoice": invoice, "payment": payment}
    response = client.get(reverse(route, args=[objects[item].pk]))
    assert response.status_code == 200
    assert response["Content-Type"] == "application/pdf"
    assert response["Cache-Control"].startswith("private, no-store")
    assert response.content.startswith(b"%PDF")
    assert len(response.content) > 5000


def test_other_kindergarten_cannot_download_document(documents):
    client, kg, child, enrollment, invoice, payment = documents
    other = Kindergarten.objects.create(name="Boshqa bog'cha")
    BillingPolicy.objects.create(kindergarten=other)
    user = User.objects.create_user(
        phone="+998900000002", password="strong-pass", full_name="Boshqa egasi",
        kindergarten=other, is_owner=True,
    )
    client.force_login(user)
    assert client.get(reverse("invoice_pdf", args=[invoice.pk])).status_code == 404
    assert client.get(reverse("payment_receipt", args=[payment.pk])).status_code == 404
    assert client.get(reverse("enrollment_contract", args=[enrollment.pk])).status_code == 404
    assert client.get(reverse("child_debt_statement", args=[child.pk])).status_code == 404
