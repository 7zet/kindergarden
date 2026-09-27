import pytest
from django.core.management import call_command

from apps.accounts.models import Role, User
from apps.school.models import BillingPolicy, Kindergarten


@pytest.mark.django_db
def test_onboard_kindergarten_creates_clean_workspace():
    call_command(
        "onboard_kindergarten", name="Yangi bog'cha", owner_name="Test Egasi",
        owner_phone="+998900001122", password="kuchli-parol",
    )
    kg = Kindergarten.objects.get(name="Yangi bog'cha")
    owner = User.objects.get(phone="+998900001122")
    assert owner.kindergarten == kg and owner.is_owner
    assert owner.check_password("kuchli-parol")
    assert BillingPolicy.objects.filter(kindergarten=kg).exists()
    assert set(Role.objects.filter(kindergarten=kg).values_list("name", flat=True)) == {
        "Direktor", "Buxgalter", "Tarbiyachi", "Qabul xodimi",
    }
    assert not kg.groups.exists()
    assert not kg.children.exists()
