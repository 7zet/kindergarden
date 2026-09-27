import uuid
from decimal import Decimal

from django.db import models
from django.db.models import Case, DecimalField, F, Sum, Value, When
from django.db.models.functions import Coalesce


class IngredientQuerySet(models.QuerySet):
    def with_stock(self):
        signed = Case(
            When(moves__direction="in", then=F("moves__quantity_g")),
            When(moves__direction="out", then=-F("moves__quantity_g")),
            default=Value(Decimal("0")), output_field=DecimalField())
        return self.annotate(stock_g=Coalesce(
            Sum(signed, filter=models.Q(moves__is_reversed=False)),
            Value(Decimal("0")), output_field=DecimalField()))


class Ingredient(models.Model):
    class Category(models.TextChoices):
        VEGETABLE = "sabzavot", "Sabzavot"
        FRUIT = "meva", "Meva"
        MEAT = "gosht", "Go'sht"
        DAIRY = "sut", "Sut mahsuloti"
        GRAIN = "don", "Don mahsuloti"
        OIL = "yog", "Yog'"
        SPICE = "ziravor", "Ziravor"
        OTHER = "boshqa", "Boshqa"

    class Unit(models.TextChoices):
        KG = "kg", "kg"
        LITRE = "litr", "litr"
        PIECE = "dona", "dona"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    kindergarten = models.ForeignKey("school.Kindergarten", on_delete=models.PROTECT,
                                     related_name="ingredients")
    name = models.CharField(max_length=120)
    category = models.CharField(max_length=20, choices=Category.choices)
    display_unit = models.CharField(max_length=10, choices=Unit.choices, default=Unit.KG)
    gram_per_piece = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    min_stock_g = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    objects = IngredientQuerySet.as_manager()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["kindergarten", "name"], name="kitchen_unique_ingredient"),
            models.CheckConstraint(condition=models.Q(min_stock_g__gte=0), name="kitchen_min_stock_nonnegative"),
        ]
        ordering = ["name"]

    @property
    def current_stock_g(self):
        from .services import stock_balance
        return stock_balance(self.kindergarten, self)

    @property
    def is_low(self):
        return self.current_stock_g < self.min_stock_g

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.display_unit == self.Unit.PIECE and not self.gram_per_piece:
            raise ValidationError({"gram_per_piece": "Donali mahsulot uchun bir dona og'irligi kerak."})

    def __str__(self): return self.name


class Supplier(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    kindergarten = models.ForeignKey("school.Kindergarten", on_delete=models.PROTECT,
                                     related_name="kitchen_suppliers")
    name = models.CharField(max_length=160)
    phone = models.CharField(max_length=20, blank=True)
    note = models.CharField(max_length=200, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["kindergarten", "name"], name="kitchen_unique_supplier")]
        ordering = ["name"]

    def __str__(self): return self.name


class Dish(models.Model):
    class MealType(models.TextChoices):
        BREAKFAST = "nonushta", "Nonushta"
        LUNCH = "tushlik", "Tushlik"
        SNACK = "gazak", "Gazak"
        DINNER = "kechki", "Kechki ovqat"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    kindergarten = models.ForeignKey("school.Kindergarten", on_delete=models.PROTECT, related_name="dishes")
    name = models.CharField(max_length=120)
    meal_type = models.CharField(max_length=12, choices=MealType.choices)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["kindergarten", "name"], name="kitchen_unique_dish")]
        ordering = ["meal_type", "name"]

    def __str__(self): return self.name


class DishIngredient(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dish = models.ForeignKey(Dish, on_delete=models.CASCADE, related_name="ingredients")
    ingredient = models.ForeignKey(Ingredient, on_delete=models.PROTECT, related_name="dish_norms")
    grams_per_child = models.DecimalField(max_digits=8, decimal_places=2)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["dish", "ingredient"], name="kitchen_unique_dish_ingredient"),
            models.CheckConstraint(condition=models.Q(grams_per_child__gt=0), name="kitchen_norm_positive"),
        ]

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.dish_id and self.ingredient_id and self.dish.kindergarten_id != self.ingredient.kindergarten_id:
            raise ValidationError("Taom va masalliq bitta bog'chaga tegishli bo'lishi kerak.")


class DailyMenu(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Qoralama"
        APPROVED = "approved", "Tasdiqlangan"
        CLOSED = "closed", "Yopilgan"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    kindergarten = models.ForeignKey("school.Kindergarten", on_delete=models.PROTECT, related_name="daily_menus")
    date = models.DateField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    children_count = models.PositiveIntegerField(default=0)
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey("accounts.User", on_delete=models.PROTECT, null=True, blank=True,
                                    related_name="approved_menus")
    fact_entered_at = models.DateTimeField(null=True, blank=True)
    note = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["kindergarten", "date"], name="kitchen_unique_daily_menu")]
        indexes = [models.Index(fields=["kindergarten", "date"])]
        ordering = ["-date"]

    def __str__(self): return f"{self.date} — {self.get_status_display()}"


class MenuDish(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    menu = models.ForeignKey(DailyMenu, on_delete=models.CASCADE, related_name="dishes")
    dish = models.ForeignKey(Dish, on_delete=models.PROTECT, related_name="menu_entries")
    meal_type = models.CharField(max_length=12, choices=Dish.MealType.choices)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["menu", "dish"], name="kitchen_unique_menu_dish")]

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.menu_id and self.dish_id and self.menu.kindergarten_id != self.dish.kindergarten_id:
            raise ValidationError("Menyu va taom bitta bog'chaga tegishli bo'lishi kerak.")


class MenuLine(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    menu = models.ForeignKey(DailyMenu, on_delete=models.CASCADE, related_name="lines")
    ingredient = models.ForeignKey(Ingredient, on_delete=models.PROTECT, related_name="menu_lines")
    planned_g = models.DecimalField(max_digits=12, decimal_places=2)
    actual_g = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["menu", "ingredient"], name="kitchen_unique_menu_line")]

    @property
    def diff_g(self): return None if self.actual_g is None else self.actual_g - self.planned_g
    @property
    def diff_pct(self):
        return None if self.actual_g is None or not self.planned_g else self.diff_g / self.planned_g * 100
    @property
    def is_over(self): return self.diff_g is not None and self.diff_g > 0


class StockMove(models.Model):
    class Direction(models.TextChoices):
        IN = "in", "Kirim"
        OUT = "out", "Chiqim"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    kindergarten = models.ForeignKey("school.Kindergarten", on_delete=models.PROTECT, related_name="stock_moves")
    ingredient = models.ForeignKey(Ingredient, on_delete=models.PROTECT, related_name="moves")
    direction = models.CharField(max_length=3, choices=Direction.choices)
    quantity_g = models.DecimalField(max_digits=12, decimal_places=2)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    happened_at = models.DateField()
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, null=True, blank=True, related_name="moves")
    document_number = models.CharField(max_length=40, blank=True)
    note = models.CharField(max_length=200, blank=True)
    source_type = models.CharField(max_length=20, default="manual")
    source_id = models.UUIDField(null=True, blank=True)
    is_reversed = models.BooleanField(default=False)
    reversal_of = models.ForeignKey("self", on_delete=models.PROTECT, null=True, blank=True, related_name="reversals")
    created_by = models.ForeignKey("accounts.User", on_delete=models.PROTECT, related_name="stock_moves")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(quantity_g__gt=0), name="kitchen_move_quantity_positive")]
        indexes = [models.Index(fields=["kindergarten", "ingredient", "happened_at"])]
        ordering = ["-happened_at", "-created_at"]

    def delete(self, *args, **kwargs):
        raise PermissionError("Ombor harakati o'chirilmaydi. Storno qiling.")

