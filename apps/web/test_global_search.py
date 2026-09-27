from datetime import date

import pytest
from django.urls import reverse

from apps.accounts.models import User
from apps.school.models import Child, Kindergarten


@pytest.mark.django_db
def test_global_search_is_tenant_scoped(client):
    own = Kindergarten.objects.create(name="Own")
    foreign = Kindergarten.objects.create(name="Foreign")
    user = User.objects.create_user(phone="+998900001234", password="x",
                                    full_name="Owner", kindergarten=own, is_owner=True)
    Child.objects.create(kindergarten=own, full_name="Ali Test", birth_date=date(2020, 1, 1))
    Child.objects.create(kindergarten=foreign, full_name="Ali Begona", birth_date=date(2020, 1, 1))
    client.force_login(user)
    response = client.get(reverse("global_search"), {"q": "Ali"})
    assert response.status_code == 200
    titles = [item["title"] for item in response.json()["results"]]
    assert "Ali Test" in titles
    assert "Ali Begona" not in titles


@pytest.mark.django_db
def test_global_search_returns_commands(client):
    kg = Kindergarten.objects.create(name="Own")
    user = User.objects.create_user(phone="+998900005678", password="x",
                                    full_name="Owner", kindergarten=kg, is_owner=True)
    client.force_login(user)
    response = client.get(reverse("global_search"), {"q": "yangi bola"})
    assert any(item["kind"] == "Amal" for item in response.json()["results"])
