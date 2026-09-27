import uuid
from datetime import date

import pytest
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.utils import timezone

from apps.accounts.models import User
from apps.attendance.models import Attendance, CheckEvent, Status
from apps.attendance.services import mark_daily_attendance
from apps.school.models import Child, Enrollment, Group, Kindergarten, Tariff


@pytest.fixture
def context(db):
    kg = Kindergarten.objects.create(name="Test")
    user = User.objects.create_user(phone="+998900000099", password="x",
                                    full_name="Operator", kindergarten=kg)
    group = Group.objects.create(kindergarten=kg, name="A")
    tariff = Tariff.objects.create(kindergarten=kg, name="T", monthly_amount=100,
                                    valid_from=date(2026, 1, 1))
    child = Child.objects.create(kindergarten=kg, full_name="Bola",
                                 birth_date=date(2020, 1, 1))
    enrollment = Enrollment.objects.create(child=child, group=group, tariff=tariff,
                                           started_at=date(2026, 1, 1))
    return user, enrollment


def test_manual_present_creates_event_and_summary(context):
    user, enrollment = context
    day = timezone.localdate()
    mark_daily_attendance(enrollment=enrollment, day=day, value="present", user=user)
    assert CheckEvent.objects.filter(enrollment=enrollment, kind="in").count() == 1
    mark = Attendance.objects.get(enrollment=enrollment, day=day)
    assert mark.status == Status.PRESENT and mark.arrived_at is not None


def test_event_day_cannot_be_cleared_or_marked_absent(context):
    user, enrollment = context
    day = timezone.localdate()
    mark_daily_attendance(enrollment=enrollment, day=day, value="present", user=user)
    with pytest.raises(ValidationError):
        mark_daily_attendance(enrollment=enrollment, day=day, value="clear", user=user)
    with pytest.raises(ValidationError):
        mark_daily_attendance(enrollment=enrollment, day=day, value="sick", user=user)


def test_audit_command_restores_summary_from_event(context):
    user, enrollment = context
    now = timezone.now()
    CheckEvent.objects.create(enrollment=enrollment, kind="in", occurred_at=now,
                              method="manual", recorded_by=user,
                              idempotency_key=uuid.uuid4())
    call_command("audit_attendance_consistency", "--fix")
    mark = Attendance.objects.get(enrollment=enrollment, day=timezone.localdate())
    assert mark.status == Status.PRESENT and mark.arrived_at is not None
