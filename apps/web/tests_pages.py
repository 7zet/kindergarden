"""Barcha sahifalar ochilishini tekshiradi (smoke test)."""

import pytest
from django.test import override_settings
from django.test import Client

from apps.billing.models import Invoice, Payment
from apps.school.models import Child, Group, WorkingCalendar
from apps.attendance.models import Attendance


@pytest.fixture(scope="module")
def seeded(django_db_setup, django_db_blocker):
    with django_db_blocker.unblock():
        from django.core.management import call_command
        call_command("seed")
        yield


@pytest.mark.django_db
def test_all_pages_open_for_owner(seeded):
    c = Client()
    assert c.login(phone="+998901112233", password="admin123")
    g = Group.objects.first()
    ch = Child.objects.first()
    inv = Invoice.objects.first()
    urls = [
        "/", "/groups/", "/groups/new/", f"/groups/{g.id}/",
        f"/groups/{g.id}/attendance/", f"/groups/{g.id}/tabel/",
        "/children/", "/children/new/", f"/children/{ch.id}/",
        f"/children/{ch.id}/enroll/", f"/children/{ch.id}/edit/",
        "/payments/", "/payments/received/", "/payments/received/new/",
        "/payments/debts/", f"/invoice/{inv.id}/", "/reports/",
        "/settings/", "/settings/tariffs/new/", "/settings/discounts/new/",
        "/settings/users/", "/settings/users/new/", "/settings/roles/new/",
        "/settings/calendar/", "/settings/audit/",
    ]
    bad = [(u, c.get(u).status_code) for u in urls if c.get(u).status_code != 200]
    assert not bad, bad


@pytest.mark.django_db
def test_month_lock_blocks_teacher(seeded):
    from apps.accounts.models import User
    teacher = User.objects.get(phone="+998901112244")
    g = Group.objects.filter(teacher=teacher).first()
    owner = Client()
    owner.login(phone="+998901112233", password="admin123")
    from django.utils import timezone
    period = timezone.localdate().strftime("%Y-%m")
    owner.post(f"/groups/{g.id}/tabel/lock/", {"period": period})

    tc = Client()
    tc.login(phone="+998901112244", password="admin123")
    enr = g.enrollments.filter(ended_at__isnull=True).first()
    day = timezone.localdate()
    r = tc.post(f"/groups/{g.id}/attendance/?day={day:%Y-%m-%d}",
                {f"s_{enr.id}": "present"}, follow=True)
    assert "yopilgan" in r.content.decode()


@pytest.mark.django_db
def test_pagination_works(seeded):
    c = Client()
    c.login(phone="+998901112233", password="admin123")
    assert c.get("/children/?page=1").status_code == 200
    assert c.get("/payments/received/?page=1").status_code == 200


@pytest.mark.django_db
def test_payment_form_rejects_negative_amount(seeded):
    c = Client()
    c.login(phone="+998901112233", password="admin123")
    child = Child.objects.first()
    response = c.post("/payments/received/new/", {
        "child": child.id, "amount": "-5000", "method": "cash",
        "received_at": "2026-08-22T10:00", "note": "xato",
    })
    assert response.status_code == 200
    assert "0.01" in response.content.decode()
    assert not Payment.objects.filter(note="xato").exists()


@pytest.mark.django_db
def test_group_form_rejects_reversed_age_range(seeded):
    c = Client()
    c.login(phone="+998901112233", password="admin123")
    response = c.post("/groups/new/", {
        "name": "Noto'g'ri yosh", "age_from": 10, "age_to": 2,
        "capacity": 20, "max_ratio": 0, "language": "uz",
        "is_active": "on",
    })
    assert response.status_code == 200
    assert "kichik bo&#x27;lmasligi" in response.content.decode()
    assert not Group.objects.filter(name="Noto'g'ri yosh").exists()


@pytest.mark.django_db
def test_non_working_day_attendance_is_blocked(seeded):
    c = Client()
    c.login(phone="+998901112233", password="admin123")
    group = Group.objects.first()
    enrollment = group.enrollments.filter(ended_at__isnull=True).first()
    day = __import__("datetime").date(2026, 8, 23)  # yakshanba
    WorkingCalendar.objects.filter(kindergarten=group.kindergarten, day=day).delete()
    response = c.post(
        f"/groups/{group.id}/attendance/?day={day:%Y-%m-%d}",
        {f"s_{enrollment.id}": "present"}, follow=True,
    )
    assert "Dam olish kunida" in response.content.decode()
    assert not Attendance.objects.filter(enrollment=enrollment, day=day).exists()


@pytest.mark.django_db
@override_settings(DEBUG=False)
def test_custom_404_does_not_leak_url_patterns():
    response = Client().get("/mavjud-bolmagan-maxfiy-manzil/")
    content = response.content.decode()
    assert response.status_code == 404
    assert "Sahifa topilmadi" in content
    assert "URL patterns" not in content


@pytest.mark.django_db
def test_owner_can_open_checkdesk_and_child_qr(seeded):
    c = Client()
    assert c.login(phone="+998901112233", password="admin123")
    child = Child.objects.first()
    assert c.get("/checkdesk/").status_code == 200
    qr = c.get(f"/children/{child.id}/qr/")
    assert qr.status_code == 200
    assert qr["Content-Type"] == "image/svg+xml"
    assert b"<svg" in qr.content
