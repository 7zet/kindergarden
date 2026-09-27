from datetime import date

import pytest

from apps.accounts.models import User
from apps.school.models import BillingPolicy, Child, Group, Kindergarten


@pytest.fixture
def ui_setup(db, client):
    kg = Kindergarten.objects.create(name="UI test bog'chasi")
    BillingPolicy.objects.create(kindergarten=kg)
    owner = User.objects.create_user(
        phone="+998909990001", password="test-pass", full_name="Egasi",
        kindergarten=kg, is_owner=True)
    teacher = User.objects.create_user(
        phone="+998909990002", password="test-pass", full_name="Tarbiyachi",
        kindergarten=kg)
    child = Child.objects.create(
        kindergarten=kg, full_name="Sinov bola", birth_date=date(2022, 1, 1))
    client.force_login(owner)
    return client, kg, teacher, child


def test_contact_create_page_has_valid_back_link(ui_setup):
    client, _, _, child = ui_setup
    response = client.get(f"/children/{child.pk}/contacts/new/")
    assert response.status_code == 200
    assert f'/children/{child.pk}/' in response.content.decode()


def test_lead_teacher_is_automatically_added_to_teachers(ui_setup):
    client, _, teacher, _ = ui_setup
    response = client.post("/groups/new/", {
        "name": "Avtomatik tarbiyachi", "capacity": 20, "max_ratio": 0,
        "language": "uz", "lead_teacher": teacher.pk, "is_active": "on",
    })
    assert response.status_code == 302
    group = Group.objects.get(name="Avtomatik tarbiyachi")
    assert group.lead_teacher == teacher
    assert group.teachers.filter(pk=teacher.pk).exists()


def test_language_is_saved_and_full_form_is_translated(ui_setup):
    client, _, _, _ = ui_setup
    response = client.post("/i18n/setlang/", {
        "language": "ru", "next": "/settings/",
    })
    assert response.status_code == 302
    assert response.cookies["django_language"].value == "ru"
    page = client.get("/children/new/").content.decode()
    assert "Дата рождения" in page
    assert "Телефон врача" in page
    assert "Сохранить" in page


def test_uzbek_cyrillic_translates_filters(ui_setup):
    client, *_ = ui_setup
    client.cookies["django_language"] = "uz-cyrl"
    page = client.get("/children/").content.decode()
    assert "Барча гуруҳлар" in page
    assert "Фильтрлаш" in page
