"""Ruxsatlar testi: har rol nimani ko'radi va nimani ko'rmaydi."""

import pytest
from django.test import Client

from apps.school.models import Child, Group


@pytest.fixture(scope="module")
def seeded(django_db_setup, django_db_blocker):
    with django_db_blocker.unblock():
        from django.core.management import call_command
        call_command("seed")
        yield


def login(phone):
    c = Client()
    assert c.login(phone=phone, password="admin123")
    return c


OWNER = "+998901112233"
TEACHER = "+998901112244"
ACCOUNTANT = "+998901112255"


@pytest.mark.django_db
def test_teacher_cannot_open_finance(seeded):
    c = login(TEACHER)
    for url in ["/payments/", "/payments/debts/", "/reports/",
                "/payments/received/new/", "/settings/", "/settings/users/"]:
        assert c.get(url).status_code == 403, url


@pytest.mark.django_db
def test_teacher_sees_only_own_groups(seeded):
    c = login(TEACHER)
    from apps.accounts.models import User
    teacher = User.objects.get(phone=TEACHER)
    own = Group.objects.filter(teacher=teacher).first()
    other = Group.objects.exclude(teacher=teacher).first()
    assert c.get(f"/groups/{own.id}/").status_code == 200
    assert c.get(f"/groups/{other.id}/").status_code == 403
    assert c.get(f"/groups/{other.id}/attendance/").status_code == 403


@pytest.mark.django_db
def test_teacher_can_mark_attendance(seeded):
    c = login(TEACHER)
    from apps.accounts.models import User
    g = Group.objects.filter(teacher=User.objects.get(phone=TEACHER)).first()
    assert c.get(f"/groups/{g.id}/attendance/").status_code == 200


@pytest.mark.django_db
def test_teacher_cannot_edit_children(seeded):
    c = login(TEACHER)
    assert c.get("/children/new/").status_code == 403
    assert c.get("/groups/new/").status_code == 403


@pytest.mark.django_db
def test_accountant_sees_finance_not_settings(seeded):
    c = login(ACCOUNTANT)
    assert c.get("/payments/").status_code == 200
    assert c.get("/payments/debts/").status_code == 200
    assert c.get("/reports/").status_code == 200
    assert c.get("/settings/").status_code == 403
    assert c.get("/settings/users/").status_code == 403


@pytest.mark.django_db
def test_owner_sees_everything(seeded):
    c = login(OWNER)
    ch = Child.objects.first()
    for url in ["/", "/groups/", "/children/", f"/children/{ch.id}/",
                "/payments/", "/payments/debts/", "/reports/",
                "/settings/", "/settings/users/"]:
        assert c.get(url).status_code == 200, url


@pytest.mark.django_db
def test_anonymous_redirected(seeded):
    c = Client()
    r = c.get("/payments/")
    assert r.status_code == 302 and "/login/" in r.url
