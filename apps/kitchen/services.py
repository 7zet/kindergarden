from collections import defaultdict
from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Case, DecimalField, F, Q, Sum, Value, When
from django.db.models.functions import Coalesce
from django.utils import timezone

from apps.accounts.audit import log as audit
from apps.attendance.models import Attendance, Status

from .models import DailyMenu, Ingredient, MenuLine, StockMove


def stock_balance(kindergarten, ingredient=None, at_date=None):
    qs = StockMove.objects.filter(kindergarten=kindergarten, is_reversed=False)
    if ingredient is not None: qs = qs.filter(ingredient=ingredient)
    if at_date is not None: qs = qs.filter(happened_at__lte=at_date)
    signed = Case(When(direction=StockMove.Direction.IN, then=F("quantity_g")),
                  When(direction=StockMove.Direction.OUT, then=-F("quantity_g")),
                  default=Value(Decimal("0")), output_field=DecimalField())
    return qs.aggregate(total=Coalesce(Sum(signed), Value(Decimal("0")),
                                       output_field=DecimalField()))["total"]


def _create_out(*, menu, ingredient, quantity, user):
    Ingredient.objects.select_for_update().get(pk=ingredient.pk)
    if stock_balance(menu.kindergarten, ingredient) < quantity:
        raise ValidationError(f"{ingredient.name}: omborda yetarli qoldiq yo'q.")
    return StockMove.objects.create(
        kindergarten=menu.kindergarten, ingredient=ingredient, direction="out",
        quantity_g=quantity, happened_at=menu.date, source_type="menu",
        source_id=menu.id, created_by=user)


@transaction.atomic
def approve_menu(menu, user):
    menu = DailyMenu.objects.select_for_update().get(pk=menu.pk)
    if menu.status != DailyMenu.Status.DRAFT:
        return menu
    count = Attendance.objects.filter(
        enrollment__child__kindergarten=menu.kindergarten,
        day=menu.date, status=Status.PRESENT).values("enrollment_id").distinct().count()
    if count < 1:
        raise ValidationError("Bu sana uchun kelgan bolalar belgilanmagan. Avval davomatni kiriting.")
    if not menu.dishes.exists():
        raise ValidationError("Tasdiqlash uchun kamida bitta taom qo'shing.")
    totals = defaultdict(Decimal)
    for entry in menu.dishes.select_related("dish").prefetch_related("dish__ingredients__ingredient"):
        for norm in entry.dish.ingredients.all():
            totals[norm.ingredient] += norm.grams_per_child * count
    if not totals:
        raise ValidationError("Tanlangan taomlarda masalliq normalari yo'q.")
    for ingredient, planned in totals.items():
        if stock_balance(menu.kindergarten, ingredient) < planned:
            raise ValidationError(f"{ingredient.name}: reja uchun omborda yetarli qoldiq yo'q.")
    for ingredient, planned in totals.items():
        MenuLine.objects.create(menu=menu, ingredient=ingredient, planned_g=planned)
        _create_out(menu=menu, ingredient=ingredient, quantity=planned, user=user)
    menu.children_count = count
    menu.status = DailyMenu.Status.APPROVED
    menu.approved_at = timezone.now()
    menu.approved_by = user
    menu.save(update_fields=["children_count", "status", "approved_at", "approved_by"])
    audit("menu.approve", menu, note=f"{count} bola", user=user)
    return menu


@transaction.atomic
def enter_fact(menu, facts, user):
    menu = DailyMenu.objects.select_for_update().get(pk=menu.pk)
    if menu.status != DailyMenu.Status.APPROVED:
        raise ValidationError("Fakt faqat tasdiqlangan menyuga kiritiladi.")
    lines = list(menu.lines.select_for_update().select_related("ingredient"))
    parsed = {}
    for line in lines:
        try: amount = Decimal(str(facts.get(str(line.ingredient_id), "")))
        except Exception: raise ValidationError(f"{line.ingredient.name}: fakt miqdori noto'g'ri.")
        if amount <= 0: raise ValidationError(f"{line.ingredient.name}: fakt musbat bo'lishi kerak.")
        parsed[line.ingredient_id] = amount
    old_moves = list(StockMove.objects.select_for_update().filter(
        kindergarten=menu.kindergarten, source_type="menu", source_id=menu.id,
        is_reversed=False))
    # Avval reja chiqimini mantiqan bekor qilib, fakt uchun qoldiqni tekshiramiz.
    available = {line.ingredient_id: stock_balance(menu.kindergarten, line.ingredient) +
                 sum((m.quantity_g for m in old_moves if m.ingredient_id == line.ingredient_id), Decimal("0"))
                 for line in lines}
    for line in lines:
        if available[line.ingredient_id] < parsed[line.ingredient_id]:
            raise ValidationError(f"{line.ingredient.name}: fakt uchun qoldiq yetarli emas.")
    for move in old_moves:
        move.is_reversed = True
        move.save(update_fields=["is_reversed"])
        StockMove.objects.create(
            kindergarten=move.kindergarten, ingredient=move.ingredient,
            direction="in" if move.direction == "out" else "out",
            quantity_g=move.quantity_g, happened_at=timezone.localdate(),
            source_type="correction", source_id=menu.id, is_reversed=True,
            reversal_of=move, note="Fakt kiritilganda reja chiqimi storno qilindi",
            created_by=user)
    for line in lines:
        line.actual_g = parsed[line.ingredient_id]
        line.save(update_fields=["actual_g"])
        _create_out(menu=menu, ingredient=line.ingredient,
                    quantity=line.actual_g, user=user)
    menu.status = DailyMenu.Status.CLOSED
    menu.fact_entered_at = timezone.now()
    menu.save(update_fields=["status", "fact_entered_at"])
    audit("menu.fact", menu, user=user)
    return menu


@transaction.atomic
def receive_stock(*, kindergarten, ingredient, quantity_g, unit_price,
                  happened_at, supplier=None, document_number="", note="", user):
    Ingredient.objects.select_for_update().get(pk=ingredient.pk)
    if ingredient.kindergarten_id != kindergarten.id:
        raise ValidationError("Masalliq boshqa bog'chaga tegishli.")
    move = StockMove.objects.create(
        kindergarten=kindergarten, ingredient=ingredient, direction="in",
        quantity_g=quantity_g, unit_price=unit_price, happened_at=happened_at,
        supplier=supplier, document_number=document_number, note=note,
        source_type="manual", created_by=user)
    audit("stock.receive", move, user=user)
    return move


@transaction.atomic
def reverse_move(move, reason, user):
    move = StockMove.objects.select_for_update().select_related("ingredient").get(pk=move.pk)
    if move.is_reversed: return move.reversals.first()
    if move.direction == "in" and stock_balance(move.kindergarten, move.ingredient) < move.quantity_g:
        raise ValidationError("Kirimni storno qilish qoldiqni manfiy qiladi.")
    move.is_reversed = True
    move.save(update_fields=["is_reversed"])
    reversal = StockMove.objects.create(
        kindergarten=move.kindergarten, ingredient=move.ingredient,
        direction="out" if move.direction == "in" else "in",
        quantity_g=move.quantity_g, happened_at=timezone.localdate(),
        source_type="correction", source_id=move.source_id, is_reversed=True,
        reversal_of=move, note=reason, created_by=user)
    audit("stock.reverse", move, note=reason, user=user)
    return reversal


def monthly_report(kindergarten, period):
    start = period.replace(day=1)
    end = (start.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
    rows = []
    for ingredient in Ingredient.objects.filter(kindergarten=kindergarten):
        moves = StockMove.objects.filter(kindergarten=kindergarten, ingredient=ingredient,
                                         is_reversed=False, happened_at__range=(start, end))
        incoming = moves.filter(direction="in").aggregate(s=Sum("quantity_g"))["s"] or Decimal("0")
        outgoing = moves.filter(direction="out").aggregate(s=Sum("quantity_g"))["s"] or Decimal("0")
        lines = MenuLine.objects.filter(menu__kindergarten=kindergarten,
                                        menu__date__range=(start, end), ingredient=ingredient)
        planned = lines.aggregate(s=Sum("planned_g"))["s"] or Decimal("0")
        actual = lines.aggregate(s=Sum("actual_g"))["s"] or Decimal("0")
        opening = stock_balance(kindergarten, ingredient, start - timedelta(days=1))
        rows.append({"ingredient": ingredient, "opening": opening, "incoming": incoming,
                     "planned": planned, "actual": actual, "diff": actual-planned,
                     "closing": opening+incoming-outgoing})
    cost = StockMove.objects.filter(kindergarten=kindergarten, direction="in", is_reversed=False,
                                    happened_at__range=(start, end), unit_price__isnull=False).aggregate(
        s=Sum(F("quantity_g") / Value(1000) * F("unit_price"))) ["s"] or Decimal("0")
    return rows, cost
