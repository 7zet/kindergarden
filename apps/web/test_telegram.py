import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

import pytest
from datetime import date
from django.test import Client, override_settings

from apps.web.telegram_views import _telegram_user
from apps.school.models import (BillingPolicy, Child, Contact, Kindergarten,
                                Person, TelegramAccount)


@override_settings(TELEGRAM_BOT_TOKEN="123456:test-token")
def test_mini_app_signature_validation():
    values = {
        "auth_date": str(int(time.time())),
        "query_id": "AAE-test",
        "user": json.dumps({"id": 123, "first_name": "Ota"}, separators=(",", ":")),
    }
    check_string = "\n".join(f"{key}={values[key]}" for key in sorted(values))
    secret = hmac.new(b"WebAppData", b"123456:test-token", hashlib.sha256).digest()
    values["hash"] = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()
    assert _telegram_user(urlencode(values))["id"] == 123
    values["hash"] = "0" * 64
    assert _telegram_user(urlencode(values)) is None


@pytest.mark.django_db
@override_settings(TELEGRAM_WEBHOOK_SECRET="very-secret")
def test_webhook_rejects_wrong_secret():
    response = Client().post(
        "/telegram/webhook/", data=json.dumps({"message": {}}),
        content_type="application/json", HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN="wrong",
    )
    assert response.status_code == 403


@pytest.mark.django_db
@override_settings(TELEGRAM_BOT_TOKEN="123456:test-token")
def test_parent_account_links_person_and_one_qr_opens_all_person_children():
    kg = Kindergarten.objects.create(name="Parent Mini")
    BillingPolicy.objects.create(kindergarten=kg)
    person = Person.objects.create(kindergarten=kg, full_name="Madina",
                                   phone="+998901234567")
    children = [Child.objects.create(kindergarten=kg, full_name=f"Bola {i}",
                                     birth_date=date(2022, 1, i + 1)) for i in range(2)]
    Contact.objects.create(child=children[0], person=person, relation="Ona",
                           kind="parent", can_pickup=True)
    Contact.objects.create(child=children[1], person=person, relation="Ona",
                           kind="parent", can_pickup=False)
    account = TelegramAccount.objects.create(telegram_user_id=321, chat_id=321)
    account.persons.add(person)
    values = {"auth_date": str(int(time.time())),
              "user": json.dumps({"id": 321, "first_name": "Ona"}, separators=(",", ":"))}
    check = "\n".join(f"{key}={values[key]}" for key in sorted(values))
    secret = hmac.new(b"WebAppData", b"123456:test-token", hashlib.sha256).digest()
    values["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    init_data = urlencode(values)
    client = Client()
    session = client.post("/telegram/mini/session/", data=json.dumps({"initData": init_data}),
                          content_type="application/json")
    assert session.status_code == 200
    assert len(session.json()["children"]) == 2
    assert len(session.json()["contacts"]) == 1
    assert {c["canPickup"] for c in session.json()["children"]} == {True, False}
    credential = client.post("/telegram/parent/credential/", data=json.dumps(
        {"initData": init_data, "contactId": str(person.id)}), content_type="application/json")
    assert credential.status_code == 200
    assert credential.json()["token"].startswith(f"p1.{person.id}.")
