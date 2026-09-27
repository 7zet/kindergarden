from datetime import date

import pytest
from django.urls import reverse

from apps.accounts.models import User
from apps.school.contact_passes import issue_contact_pass
from apps.school.models import (BillingPolicy, Child, Contact, Kindergarten,
                                Person, TelegramAccount)


@pytest.fixture
def person_setup(db, client):
    kg = Kindergarten.objects.create(name="Person test")
    BillingPolicy.objects.create(kindergarten=kg)
    owner = User.objects.create_user(phone="+998900001122", password="password",
                                     full_name="Egasi", kindergarten=kg, is_owner=True)
    children = [Child.objects.create(kindergarten=kg, full_name=f"Bola {i}",
                                     birth_date=date(2022, 1, i + 1)) for i in range(3)]
    client.force_login(owner)
    return client, kg, owner, children


def test_contact_form_creates_person_then_links_existing_with_independent_permissions(person_setup):
    client, kg, owner, children = person_setup
    common = {"full_name": "Aliyeva Madina", "phone": "+998 90 123 45 67",
              "relation": "Ona", "kind": "parent", "receives_messages": "on"}
    response = client.post(reverse("contact_new", args=[children[0].id]),
                           {**common, "can_pickup": "on", "is_primary": "on"})
    assert response.status_code == 302
    person = Person.objects.get(full_name="Aliyeva Madina")
    response = client.post(reverse("contact_new", args=[children[1].id]), {
        "existing_person": str(person.id), "full_name": "", "phone": "",
        "relation": "Ona", "kind": "parent", "is_payer": "on",
        "receives_messages": "on",
    })
    assert response.status_code == 302
    links = list(person.contacts.order_by("child__full_name"))
    assert len(links) == 2
    assert links[0].can_pickup is True and links[0].is_payer is False
    assert links[1].can_pickup is False and links[1].is_payer is True
    person.refresh_from_db()
    assert person.phone == "+998 90 123 45 67"  # bo'sh forma eski telefonni o'chirmaydi


def test_same_phone_is_not_identity(person_setup):
    client, kg, owner, children = person_setup
    first = Contact.objects.create(child=children[0], full_name="Ona", phone="+998901112233",
                                   relation="Ona", kind="parent")
    second = Contact.objects.create(child=children[1], full_name="Ota", phone="998901112233",
                                    relation="Ota", kind="parent")
    assert first.person_id != second.person_id
    assert first.person.normalized_phone == second.person.normalized_phone


def test_explicit_merge_moves_links_and_telegram_but_blocks_child_conflict(person_setup):
    client, kg, owner, children = person_setup
    source = Person.objects.create(kindergarten=kg, full_name="Madina A", phone="+998901234567")
    target = Person.objects.create(kindergarten=kg, full_name="Madina Aliyeva", phone="+998901234567")
    Contact.objects.create(child=children[0], person=source, relation="Ona", kind="parent")
    Contact.objects.create(child=children[1], person=target, relation="Ona", kind="parent")
    account = TelegramAccount.objects.create(telegram_user_id=123, chat_id=123)
    account.persons.add(source)
    pass_item, _ = issue_contact_pass(source)
    response = client.post(reverse("person_merge", args=[source.id]), {"target": target.id})
    assert response.status_code == 302
    source.refresh_from_db(); pass_item.refresh_from_db(); account.refresh_from_db()
    assert not source.is_active and pass_item.used_at is not None
    assert set(target.contacts.values_list("child_id", flat=True)) == {children[0].id, children[1].id}
    assert account.persons.filter(pk=target.pk).exists() and not account.persons.filter(pk=source.pk).exists()

    duplicate = Person.objects.create(kindergarten=kg, full_name="Dubl", phone="+998900000000")
    Contact.objects.create(child=children[0], person=duplicate, relation="Buvi", kind="family")
    response = client.post(reverse("person_merge", args=[duplicate.id]), {"target": target.id})
    duplicate.refresh_from_db()
    assert response.status_code == 302 and duplicate.is_active
