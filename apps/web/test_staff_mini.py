import hashlib
import hmac
import json
import time
from datetime import date
from urllib.parse import urlencode

import pytest
from django.test import Client, override_settings

from apps.accounts.models import User
from apps.attendance.models import Attendance, CheckEvent
from apps.school.contact_passes import issue_contact_pass
from apps.school.models import (BillingPolicy, Child, Contact, Enrollment, Group,
                                Kindergarten, Person, StaffTelegramAccount, Tariff)


TOKEN = "123456:test-token"


def init_data(user_id):
    values = {"auth_date": str(int(time.time())),
              "user": json.dumps({"id": user_id, "first_name": "Xodim"},
                                 separators=(",", ":"))}
    check = "\n".join(f"{key}={values[key]}" for key in sorted(values))
    secret = hmac.new(b"WebAppData", TOKEN.encode(), hashlib.sha256).digest()
    values["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return urlencode(values)


@pytest.mark.django_db
@override_settings(TELEGRAM_BOT_TOKEN=TOKEN)
def test_staff_resolve_then_confirm_records_contact_and_multiple_children():
    kg = Kindergarten.objects.create(name="Mini")
    BillingPolicy.objects.create(kindergarten=kg)
    staff = User.objects.create_user(phone="+998900000001", password="password",
        full_name="Direktor", kindergarten=kg, is_owner=True)
    StaffTelegramAccount.objects.create(user=staff, telegram_user_id=777, chat_id=777)
    tariff = Tariff.objects.create(kindergarten=kg, name="Tarif", monthly_amount=100,
                                   valid_from=date(2026, 1, 1))
    group = Group.objects.create(kindergarten=kg, name="Guruh", default_tariff=tariff)
    person = Person.objects.create(kindergarten=kg, full_name="Aliyeva Madina",
                                   phone="+998901234567")
    enrollments, contacts = [], []
    for index in range(2):
        child = Child.objects.create(kindergarten=kg, full_name=f"Bola {index}",
                                     birth_date=date(2022, 1, 1),
                                     allergies="Yong'oq" if index == 0 else "")
        enrollments.append(Enrollment.objects.create(
            child=child, group=group, tariff=tariff, started_at=date(2026, 1, 1)))
        contacts.append(Contact.objects.create(
            child=child, person=person, relation="Ona",
            kind="parent", can_pickup=True))
    _, token = issue_contact_pass(contacts[0])
    client = Client(); auth = init_data(777)
    response = client.post("/telegram/staff/resolve/", data=json.dumps(
        {"initData": auth, "token": token, "kind": "in"}),
        content_type="application/json")
    assert response.status_code == 200
    assert len(response.json()["children"]) == 2
    assert any(c["allergies"] == "Yong'oq" for c in response.json()["children"])
    ids = [str(e.id) for e in enrollments]
    response = client.post("/telegram/staff/confirm/", data=json.dumps({
        "initData": auth, "token": token, "kind": "in", "enrollmentIds": ids,
        "idempotency": {value: str(__import__('uuid').uuid4()) for value in ids},
    }), content_type="application/json")
    assert response.status_code == 200 and response.json()["count"] == 2
    assert Attendance.objects.count() == 2
    assert set(CheckEvent.objects.values_list("contact_id", flat=True)) == {c.id for c in contacts}
