from datetime import date

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.accounts.models import User
from apps.attendance.models import Attendance, CheckEvent
from apps.attendance.services import check_in, check_out
from apps.school.models import (BillingPolicy, Child, Contact, Enrollment, Group,
                                Kindergarten, Tariff)


@pytest.fixture
def check_setup(db):
    kg = Kindergarten.objects.create(name="Check bog'cha")
    BillingPolicy.objects.create(kindergarten=kg)
    user = User.objects.create_user(
        phone="+998900009999", password="password", full_name="Navbatchi",
        kindergarten=kg, is_owner=True,
    )
    tariff = Tariff.objects.create(
        kindergarten=kg, name="Tarif", monthly_amount=100,
        valid_from=date(2026, 1, 1),
    )
    group = Group.objects.create(kindergarten=kg, name="Guruh", default_tariff=tariff)
    child = Child.objects.create(
        kindergarten=kg, full_name="Bola", birth_date=date(2022, 1, 1),
    )
    enrollment = Enrollment.objects.create(
        child=child, group=group, tariff=tariff, started_at=date(2026, 1, 1),
    )
    return user, enrollment


def test_checkin_and_checkout_sync_attendance(check_setup):
    user, enrollment = check_setup
    check_in(enrollment=enrollment, user=user, method=CheckEvent.Method.QR)
    check_out(enrollment=enrollment, user=user, method=CheckEvent.Method.MANUAL,
              note="Olib ketuvchi navbatchi tomonidan tekshirildi")
    mark = Attendance.objects.get(enrollment=enrollment, day=timezone.localdate())
    assert mark.arrived_at and mark.left_at
    assert list(CheckEvent.objects.values_list("kind", flat=True)) == ["out", "in"]


def test_duplicate_checkin_is_rejected(check_setup):
    user, enrollment = check_setup
    check_in(enrollment=enrollment, user=user)
    with pytest.raises(ValidationError, match="allaqachon"):
        check_in(enrollment=enrollment, user=user)
    assert CheckEvent.objects.count() == 1


def test_checkout_before_checkin_is_rejected(check_setup):
    user, enrollment = check_setup
    with pytest.raises(ValidationError, match="oldin"):
        check_out(enrollment=enrollment, user=user)
    assert not CheckEvent.objects.exists()


def test_unauthorized_contact_requires_director_override_and_reason(check_setup):
    user, enrollment = check_setup
    contact = Contact.objects.create(
        child=enrollment.child, full_name="Amaki", relation="Amaki",
        phone="+998901111111", kind="emergency", can_pickup=False,
    )
    check_in(enrollment=enrollment, user=user, contact=contact)
    with pytest.raises(ValidationError, match="ruxsat etilmagan"):
        check_out(enrollment=enrollment, user=user, pickup_contact=contact)
    event = check_out(
        enrollment=enrollment, user=user, pickup_contact=contact,
        override_by=user, override_reason="Direktor ota-ona bilan telefon orqali tasdiqladi",
    )
    assert event.is_override and event.override_by == user
