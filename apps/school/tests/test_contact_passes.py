from datetime import date

import pytest

from apps.school.contact_passes import (issue_contact_pass, resolve_signed_token,
                                        sibling_contacts)
from apps.school.models import (BillingPolicy, Child, Contact, Kindergarten, Person)


@pytest.mark.django_db
def test_contact_qr_is_signed_rotating_and_contact_specific():
    kg = Kindergarten.objects.create(name="QR bog'cha")
    BillingPolicy.objects.create(kindergarten=kg)
    child = Child.objects.create(kindergarten=kg, full_name="Bola",
                                 birth_date=date(2022, 1, 1))
    contact = Contact.objects.create(child=child, full_name="Ona", relation="Ona",
                                     phone="+998 90 123-45-67", kind="parent")
    first, first_token = issue_contact_pass(contact)
    second, second_token = issue_contact_pass(contact)
    assert resolve_signed_token(first_token) == first
    assert resolve_signed_token(second_token).person == contact.person
    payload, signature = second_token.rsplit(".", 1)
    tampered = payload + "." + ("0" if signature[0] != "0" else "1") + signature[1:]
    assert resolve_signed_token(tampered) is None
    assert second.code.isdigit() and len(second.code) == 6


@pytest.mark.django_db
def test_same_phone_does_not_merge_people_but_same_person_opens_multiple_children():
    kg = Kindergarten.objects.create(name="Bir")
    other = Kindergarten.objects.create(name="Ikki")
    BillingPolicy.objects.bulk_create([BillingPolicy(kindergarten=kg),
                                       BillingPolicy(kindergarten=other)])
    shared = Person.objects.create(kindergarten=kg, full_name="Bir ona",
                                   phone="+998 90 111 22 33")
    contacts = []
    for index, school in enumerate([kg, kg]):
        child = Child.objects.create(kindergarten=school, full_name=f"Bola {index}",
                                     birth_date=date(2022, 1, 1))
        contacts.append(Contact.objects.create(child=child, person=shared,
                                               relation="Ona", kind="parent"))
    other_child = Child.objects.create(kindergarten=kg, full_name="Boshqa bola",
                                       birth_date=date(2022, 1, 1))
    same_phone_other_person = Contact.objects.create(
        child=other_child, full_name="Boshqa odam", relation="Ota",
        phone="998901112233", kind="parent")
    found = sibling_contacts(contacts[0])
    assert {c.child.kindergarten_id for c in found} == {kg.id}
    assert len(found) == 2
    assert same_phone_other_person not in found
