from datetime import date
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.urls import reverse

from apps.accounts.models import User
from apps.attendance.models import Attendance, Status
from apps.kitchen.models import DailyMenu, Dish, DishIngredient, Ingredient, MenuDish, StockMove
from apps.kitchen.services import approve_menu, enter_fact, receive_stock, reverse_move, stock_balance
from apps.school.models import Child, Enrollment, Group, Kindergarten, Tariff


@pytest.fixture
def kitchen(db):
    kg = Kindergarten.objects.create(name="Sinov bog'chasi")
    owner = User.objects.create_user(phone="+998900001111", password="test-pass-123", full_name="Egasi", kindergarten=kg, is_owner=True)
    tariff = Tariff.objects.create(kindergarten=kg, name="Tarif", monthly_amount=1000000, valid_from=date(2026, 1, 1))
    group = Group.objects.create(kindergarten=kg, name="Guruh", default_tariff=tariff)
    child = Child.objects.create(kindergarten=kg, full_name="Bola", birth_date=date(2022, 1, 1))
    enrollment = Enrollment.objects.create(child=child, group=group, tariff=tariff, started_at=date(2026, 1, 1))
    Attendance.objects.create(enrollment=enrollment, day=date(2026, 9, 15), status=Status.PRESENT)
    rice = Ingredient.objects.create(kindergarten=kg, name="Guruch", category="don")
    meat = Ingredient.objects.create(kindergarten=kg, name="Go'sht", category="gosht")
    receive_stock(kindergarten=kg, ingredient=rice, quantity_g=10000, unit_price=20000, happened_at=date(2026, 9, 15), user=owner)
    receive_stock(kindergarten=kg, ingredient=meat, quantity_g=10000, unit_price=80000, happened_at=date(2026, 9, 15), user=owner)
    dish = Dish.objects.create(kindergarten=kg, name="Palov", meal_type="tushlik")
    DishIngredient.objects.create(dish=dish, ingredient=rice, grams_per_child=80)
    DishIngredient.objects.create(dish=dish, ingredient=meat, grams_per_child=50)
    menu = DailyMenu.objects.create(kindergarten=kg, date=date(2026, 9, 15))
    MenuDish.objects.create(menu=menu, dish=dish, meal_type=dish.meal_type)
    return kg, owner, rice, meat, dish, menu, enrollment


@pytest.mark.django_db
def test_plan_is_norm_times_attendance(kitchen):
    menu = kitchen[5]; approve_menu(menu, kitchen[1])
    assert menu.lines.get(ingredient=kitchen[2]).planned_g == 80


@pytest.mark.django_db
def test_same_ingredient_from_two_dishes_is_added(kitchen):
    kg, owner, rice, _, _, menu, _ = kitchen
    soup = Dish.objects.create(kindergarten=kg, name="Sho'rva", meal_type="tushlik")
    DishIngredient.objects.create(dish=soup, ingredient=rice, grams_per_child=20)
    MenuDish.objects.create(menu=menu, dish=soup, meal_type=soup.meal_type)
    approve_menu(menu, owner)
    assert menu.lines.get(ingredient=rice).planned_g == 100


@pytest.mark.django_db
def test_plan_stays_frozen_after_attendance_change(kitchen):
    _, owner, rice, _, _, menu, enrollment = kitchen; approve_menu(menu, owner)
    Attendance.objects.filter(enrollment=enrollment, day=menu.date).update(status=Status.ABSENT)
    assert menu.lines.get(ingredient=rice).planned_g == 80
    menu.refresh_from_db(); assert menu.children_count == 1


@pytest.mark.django_db
def test_double_approval_does_not_duplicate_moves(kitchen):
    kg, owner, _, _, _, menu, _ = kitchen; approve_menu(menu, owner); approve_menu(menu, owner)
    assert StockMove.objects.filter(kindergarten=kg, source_id=menu.id, direction="out", is_reversed=False).count() == 2


@pytest.mark.django_db
def test_insufficient_stock_rolls_back_approval(kitchen):
    _, owner, rice, _, _, menu, _ = kitchen; StockMove.objects.filter(ingredient=rice).update(quantity_g=10)
    with pytest.raises(ValidationError): approve_menu(menu, owner)
    menu.refresh_from_db(); assert menu.status == "draft" and not menu.lines.exists()


@pytest.mark.django_db
def test_fact_reverses_plan_moves(kitchen):
    _, owner, rice, meat, _, menu, _ = kitchen; approve_menu(menu, owner); enter_fact(menu, {str(rice.id):90, str(meat.id):60}, owner)
    assert StockMove.objects.filter(source_id=menu.id, is_reversed=True, reversal_of__isnull=True).count() == 2


@pytest.mark.django_db
def test_fact_creates_actual_outgoing(kitchen):
    _, owner, rice, meat, _, menu, _ = kitchen; approve_menu(menu, owner); enter_fact(menu, {str(rice.id):90, str(meat.id):60}, owner)
    assert StockMove.objects.get(source_id=menu.id, ingredient=rice, direction="out", is_reversed=False).quantity_g == 90


@pytest.mark.django_db
def test_stock_balance_is_in_minus_out(kitchen):
    kg, owner, rice, _, _, menu, _ = kitchen; approve_menu(menu, owner)
    assert stock_balance(kg, rice) == 9920


@pytest.mark.django_db
def test_reversed_move_does_not_affect_balance(kitchen):
    kg, owner, rice, *_ = kitchen; reverse_move(StockMove.objects.filter(ingredient=rice, direction="in").first(), "xato", owner)
    assert stock_balance(kg, rice) == 0


@pytest.mark.django_db
def test_stock_move_cannot_be_deleted(kitchen):
    with pytest.raises(PermissionError): StockMove.objects.first().delete()


@pytest.mark.django_db
def test_quantity_constraint_rejects_nonpositive(kitchen):
    kg, owner, rice, *_ = kitchen
    with pytest.raises(IntegrityError), transaction.atomic():
        StockMove.objects.create(kindergarten=kg, ingredient=rice, direction="in", quantity_g=0, happened_at=date.today(), created_by=owner)


@pytest.mark.django_db
def test_other_tenant_ingredient_returns_404(kitchen, client):
    kg, owner, *_ = kitchen; other=Kindergarten.objects.create(name="Begona")
    foreign=Ingredient.objects.create(kindergarten=other, name="Begona", category="boshqa")
    client.force_login(owner)
    assert client.get(reverse("kitchen_ingredient_edit", kwargs={"pk":foreign.pk}), HTTP_HOST="127.0.0.1").status_code == 404


@pytest.mark.django_db
def test_user_without_permission_gets_403(kitchen, client):
    kg, *_ = kitchen; user=User.objects.create_user(phone="+998900009999", password="pass-test-123", full_name="Ruxsatsiz", kindergarten=kg)
    client.force_login(user)
    assert client.get(reverse("kitchen_menu"), HTTP_HOST="127.0.0.1").status_code == 403

