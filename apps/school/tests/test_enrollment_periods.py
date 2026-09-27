from datetime import date
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from apps.school.models import Child, Enrollment, Group, Kindergarten, Tariff
from apps.school.services import create_enrollment
from apps.web.forms import EnrollmentForm


@pytest.fixture
def enrollment_data(db):
    kg = Kindergarten.objects.create(name="Test bog'cha")
    tariff = Tariff.objects.create(
        kindergarten=kg, name="Standart", monthly_amount=Decimal("1000000"),
        valid_from=date(2026, 1, 1))
    group = Group.objects.create(
        kindergarten=kg, name="Kichkintoy", age_from=3, age_to=5,
        capacity=2, default_tariff=tariff)
    child = Child.objects.create(
        kindergarten=kg, full_name="Ali Test", birth_date=date(2022, 6, 1))
    return kg, tariff, group, child


@pytest.mark.django_db
def test_future_end_date_remains_effective(enrollment_data, monkeypatch):
    _, tariff, group, child = enrollment_data
    enrollment = Enrollment.objects.create(
        child=child, group=group, tariff=tariff,
        started_at=date(2026, 9, 1), ended_at=date(2026, 12, 31))
    monkeypatch.setattr("django.utils.timezone.localdate", lambda: date(2026, 9, 14))

    assert enrollment.status == "active"
    assert enrollment.is_open
    assert group.enrollments.effective_on().get() == enrollment
    assert group.active_count == 1
    assert child.current_enrollment == enrollment


@pytest.mark.django_db
def test_future_contract_is_reservation(enrollment_data, monkeypatch):
    _, tariff, group, child = enrollment_data
    enrollment = Enrollment.objects.create(
        child=child, group=group, tariff=tariff,
        started_at=date(2026, 10, 1), ended_at=date(2027, 5, 31))
    monkeypatch.setattr("django.utils.timezone.localdate", lambda: date(2026, 9, 14))

    assert enrollment.status == "enrolled"
    assert group.reserved_count == 1
    assert child.current_enrollment == enrollment


@pytest.mark.django_db
def test_create_enrollment_rejects_overlapping_contract(enrollment_data):
    _, tariff, group, child = enrollment_data
    Enrollment.objects.create(
        child=child, group=group, tariff=tariff,
        started_at=date(2026, 1, 1), ended_at=date(2026, 12, 31))

    with pytest.raises(ValidationError, match="kesishadigan shartnoma"):
        create_enrollment(
            child=child, group=group, tariff=tariff,
            started_at=date(2026, 9, 1), ended_at=date(2026, 11, 30))


@pytest.mark.django_db
def test_create_enrollment_rejects_full_group(enrollment_data):
    kg, tariff, group, child = enrollment_data
    for index in range(2):
        other = Child.objects.create(
            kindergarten=kg, full_name=f"Bola {index}", birth_date=date(2022, 1, 1))
        Enrollment.objects.create(
            child=other, group=group, tariff=tariff, started_at=date(2026, 1, 1))

    with pytest.raises(ValidationError, match="bo'sh joy yo'q"):
        create_enrollment(
            child=child, group=group, tariff=tariff, started_at=date(2026, 9, 1))


@pytest.mark.django_db
def test_disjoint_contracts_do_not_overcount_capacity(enrollment_data):
    kg, tariff, group, child = enrollment_data
    group.capacity = 1
    group.save(update_fields=["capacity"])
    first = Child.objects.create(
        kindergarten=kg, full_name="Yanvar bolasi", birth_date=date(2022, 1, 1))
    second = Child.objects.create(
        kindergarten=kg, full_name="Mart bolasi", birth_date=date(2022, 1, 1))
    Enrollment.objects.create(child=first, group=group, tariff=tariff,
                              started_at=date(2026, 1, 1), ended_at=date(2026, 1, 31))
    Enrollment.objects.create(child=second, group=group, tariff=tariff,
                              started_at=date(2026, 3, 1), ended_at=date(2026, 3, 31))

    enrollment = create_enrollment(
        child=child, group=group, tariff=tariff,
        started_at=date(2026, 2, 1), ended_at=date(2026, 2, 28))
    assert enrollment.pk


@pytest.mark.django_db
def test_enrollment_form_requires_age_mismatch_confirmation(enrollment_data):
    _, tariff, group, child = enrollment_data
    child.birth_date = date(2018, 1, 1)
    child.save(update_fields=["birth_date"])
    data = {
        "group": group.pk, "tariff": tariff.pk, "discount": "",
        "started_at": "2026-09-14", "ended_at": "",
    }
    form = EnrollmentForm(data, child=child)
    form.fields["group"].queryset = Group.objects.all()
    form.fields["tariff"].queryset = Tariff.objects.all()
    assert not form.is_valid()
    assert "8 yosh" in str(form.errors["group"])

    data["allow_age_mismatch"] = "on"
    form = EnrollmentForm(data, child=child)
    form.fields["group"].queryset = Group.objects.all()
    form.fields["tariff"].queryset = Tariff.objects.all()
    assert form.is_valid(), form.errors
