import pytest
from django.contrib.auth.models import Permission
from django.test import Client

from apps.accounts.models import AuditLog, Role, User
from apps.school.models import BillingPolicy, Kindergarten, StaffTelegramAccount


@pytest.fixture
def users(db, client):
    kg = Kindergarten.objects.create(name="User management test")
    BillingPolicy.objects.create(kindergarten=kg)
    owner = User.objects.create_user(
        phone="+998900001001", password="Owner-pass-123", full_name="Egasi",
        kindergarten=kg, is_owner=True,
    )
    role = Role.objects.create(kindergarten=kg, name="Tarbiyachi")
    staff = User.objects.create_user(
        phone="+998900001002", password="Staff-pass-123", full_name="Xodim",
        kindergarten=kg, role=role,
    )
    client.force_login(owner)
    return client, kg, owner, staff, role


def test_owner_can_edit_staff_without_touching_password(users):
    client, _, _, staff, role = users
    old_hash = staff.password
    response = client.post(f"/settings/users/{staff.pk}/edit/", {
        "full_name": "Yangilangan Xodim", "phone": staff.phone,
        "role": role.pk, "is_active": "on",
    })
    assert response.status_code == 302
    staff.refresh_from_db()
    assert staff.full_name == "Yangilangan Xodim"
    assert staff.password == old_hash
    assert AuditLog.objects.filter(action="user.update", object_id=str(staff.pk)).exists()


def test_password_reset_is_hashed_forces_change_and_unlinks_sessions(users):
    client, _, _, staff, _ = users
    staff_client = Client()
    assert staff_client.login(phone=staff.phone, password="Staff-pass-123")
    response = client.post(f"/settings/users/{staff.pk}/password/", {
        "password": "New-staff-pass-456", "password_confirm": "New-staff-pass-456",
        "require_change": "on",
    })
    assert response.status_code == 302
    staff.refresh_from_db()
    assert staff.check_password("New-staff-pass-456")
    assert "New-staff-pass-456" not in staff.password
    assert staff.must_change_password is True
    assert staff_client.get("/").status_code == 302
    log = AuditLog.objects.get(action="user.password_reset", object_id=str(staff.pk))
    assert "New-staff-pass-456" not in str(log.after)


def test_forced_user_can_only_change_own_password(users):
    _, _, _, staff, _ = users
    staff.must_change_password = True
    staff.save(update_fields=["must_change_password"])
    staff_client = Client()
    assert staff_client.login(phone=staff.phone, password="Staff-pass-123")
    response = staff_client.get("/")
    assert response.status_code == 302
    assert response.url == "/settings/account/password/"
    response = staff_client.post("/settings/account/password/", {
        "old_password": "Staff-pass-123", "password": "Own-new-pass-789",
        "password_confirm": "Own-new-pass-789",
    })
    assert response.status_code == 302
    staff.refresh_from_db()
    assert staff.must_change_password is False
    assert str(staff_client.session.get("_auth_user_id")) == str(staff.pk)
    assert staff_client.get("/").status_code == 403  # majburiy parol sahifasiga qaytmaydi


def test_owner_account_is_protected_from_other_manager(users):
    _, kg, owner, _, _ = users
    manager_role = Role.objects.create(kindergarten=kg, name="Direktor")
    manager_role.permissions.add(Permission.objects.get(codename="add_user"))
    manager = User.objects.create_user(
        phone="+998900001003", password="Manager-pass-123", full_name="Direktor",
        kindergarten=kg, role=manager_role,
    )
    manager_client = Client()
    manager_client.force_login(manager)
    assert manager_client.get(f"/settings/users/{owner.pk}/edit/").status_code == 403


def test_role_can_be_edited_and_empty_role_deleted(users):
    client, kg, _, _, role = users
    permission = Permission.objects.get(codename="view_child")
    response = client.post(f"/settings/roles/{role.pk}/edit/", {
        "name": "Katta tarbiyachi", "permissions": [permission.pk],
    })
    assert response.status_code == 302
    role.refresh_from_db()
    assert role.name == "Katta tarbiyachi"
    assert role.permissions.filter(pk=permission.pk).exists()

    empty = Role.objects.create(kindergarten=kg, name="Vaqtinchalik")
    response = client.post(f"/settings/roles/{empty.pk}/delete/")
    assert response.status_code == 302
    assert not Role.objects.filter(pk=empty.pk).exists()


def test_telegram_account_can_be_unlinked(users):
    client, _, _, staff, _ = users
    StaffTelegramAccount.objects.create(user=staff, telegram_user_id=991, chat_id=991)
    response = client.post(f"/settings/users/{staff.pk}/telegram/unlink/")
    assert response.status_code == 302
    assert not StaffTelegramAccount.objects.filter(user=staff).exists()
