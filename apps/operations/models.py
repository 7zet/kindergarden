import uuid
from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q


class ExpenseCategory(models.Model):
    class Kind(models.TextChoices):
        FOOD = "food", "Oziq-ovqat"
        RENT = "rent", "Ijara"
        UTILITIES = "utilities", "Kommunal"
        HOUSEHOLD = "household", "Xo'jalik"
        SALARY = "salary", "Ish haqi"
        EDUCATION = "education", "Ta'lim xarajati"
        OTHER = "other", "Boshqa"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    kindergarten = models.ForeignKey("school.Kindergarten", on_delete=models.CASCADE,
                                     related_name="expense_categories")
    name = models.CharField("Nomi", max_length=100)
    kind = models.CharField("Turi", max_length=16, choices=Kind.choices)
    is_active = models.BooleanField("Faol", default=True)

    class Meta:
        unique_together = [("kindergarten", "name")]
        ordering = ["kind", "name"]

    def __str__(self):
        return self.name


class Supplier(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    kindergarten = models.ForeignKey("school.Kindergarten", on_delete=models.CASCADE,
                                     related_name="suppliers")
    name = models.CharField("Nomi", max_length=160)
    inn = models.CharField("STIR", max_length=20, blank=True)
    phone = models.CharField("Telefon", max_length=20, blank=True)
    bank_account = models.CharField("Hisob raqami", max_length=32, blank=True)
    note = models.CharField("Izoh", max_length=200, blank=True)
    is_active = models.BooleanField("Faol", default=True)

    class Meta:
        unique_together = [("kindergarten", "name")]
        ordering = ["name"]

    def __str__(self):
        return self.name


class MoneyMethod(models.TextChoices):
    CASH = "cash", "Naqd"
    CARD = "card", "Karta"
    TRANSFER = "transfer", "Bank o'tkazmasi"


class Expense(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    kindergarten = models.ForeignKey("school.Kindergarten", on_delete=models.PROTECT,
                                     related_name="expenses")
    category = models.ForeignKey(ExpenseCategory, on_delete=models.PROTECT,
                                 related_name="expenses", verbose_name="Kategoriya")
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, null=True, blank=True,
                                 related_name="expenses", verbose_name="Yetkazib beruvchi")
    group = models.ForeignKey("school.Group", on_delete=models.PROTECT, null=True, blank=True,
                              related_name="expenses", verbose_name="Guruh")
    title = models.CharField("Xarajat nomi", max_length=180)
    amount = models.DecimalField("Summa", max_digits=14, decimal_places=2,
                                 validators=[MinValueValidator(Decimal("0.01"))])
    method = models.CharField("To'lov usuli", max_length=12, choices=MoneyMethod.choices)
    paid_at = models.DateTimeField("To'langan vaqt")
    document_number = models.CharField("Hujjat raqami", max_length=80, blank=True)
    note = models.TextField("Izoh", blank=True)
    is_void = models.BooleanField("Bekor qilingan", default=False)
    created_by = models.ForeignKey("accounts.User", on_delete=models.PROTECT,
                                   related_name="created_expenses")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-paid_at", "-created_at"]
        constraints = [models.CheckConstraint(condition=Q(amount__gt=0),
                                               name="expense_amount_positive")]
        indexes = [models.Index(fields=["kindergarten", "paid_at"])]


class CashShift(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Ochiq"
        CLOSED = "closed", "Yopilgan"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    kindergarten = models.ForeignKey("school.Kindergarten", on_delete=models.PROTECT,
                                     related_name="cash_shifts")
    cashier = models.ForeignKey("accounts.User", on_delete=models.PROTECT,
                                related_name="cash_shifts")
    opened_at = models.DateTimeField(auto_now_add=True)
    opening_balance = models.DecimalField(max_digits=14, decimal_places=2, default=0,
                                          validators=[MinValueValidator(0)])
    closed_at = models.DateTimeField(null=True, blank=True)
    expected_balance = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    actual_balance = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True,
                                         validators=[MinValueValidator(0)])
    difference = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.OPEN)
    close_note = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["-opened_at"]
        constraints = [models.UniqueConstraint(
            fields=["kindergarten"], condition=Q(status="open"), name="one_open_cash_shift_per_kg"),
            models.CheckConstraint(condition=Q(opening_balance__gte=0),
                                   name="cash_shift_opening_nonnegative")]


class StaffCompensation(models.Model):
    user = models.OneToOneField("accounts.User", on_delete=models.CASCADE,
                                related_name="compensation")
    monthly_salary = models.DecimalField("Oylik maosh", max_digits=14, decimal_places=2,
                                         validators=[MinValueValidator(0)])
    effective_from = models.DateField("Amal qilish sanasi")
    note = models.CharField("Izoh", max_length=200, blank=True)


class PayrollEntry(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Qoralama"
        APPROVED = "approved", "Tasdiqlangan"
        PAID = "paid", "To'langan"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    kindergarten = models.ForeignKey("school.Kindergarten", on_delete=models.PROTECT,
                                     related_name="payroll_entries")
    employee = models.ForeignKey("accounts.User", on_delete=models.PROTECT,
                                 related_name="payroll_entries")
    period = models.DateField("Davr")
    base_salary = models.DecimalField("Asosiy maosh", max_digits=14, decimal_places=2,
                                      validators=[MinValueValidator(0)])
    advance = models.DecimalField("Avans", max_digits=14, decimal_places=2, default=0,
                                  validators=[MinValueValidator(0)])
    bonus = models.DecimalField("Bonus", max_digits=14, decimal_places=2, default=0,
                                validators=[MinValueValidator(0)])
    penalty = models.DecimalField("Jarima", max_digits=14, decimal_places=2, default=0,
                                  validators=[MinValueValidator(0)])
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    paid_at = models.DateTimeField(null=True, blank=True)
    method = models.CharField(max_length=12, choices=MoneyMethod.choices, blank=True)
    note = models.CharField(max_length=200, blank=True)
    created_by = models.ForeignKey("accounts.User", on_delete=models.PROTECT,
                                   related_name="created_payroll_entries")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("kindergarten", "employee", "period")]
        ordering = ["-period", "employee__full_name"]

    @property
    def net_amount(self):
        return self.base_salary + self.bonus - self.penalty - self.advance


class NotificationOutbox(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Navbatda"
        SENDING = "sending", "Yuborilmoqda"
        SENT = "sent", "Yuborildi"
        FAILED = "failed", "Xato"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    kindergarten = models.ForeignKey("school.Kindergarten", on_delete=models.CASCADE,
                                     related_name="notification_outbox")
    chat_id = models.BigIntegerField()
    kind = models.CharField(max_length=32)
    text = models.TextField()
    dedupe_key = models.CharField(max_length=160, unique=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    attempts = models.PositiveSmallIntegerField(default=0)
    available_at = models.DateTimeField()
    sent_at = models.DateTimeField(null=True, blank=True)
    last_error = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["available_at"]
        indexes = [models.Index(fields=["status", "available_at"])]


class ServiceHeartbeat(models.Model):
    """Fon worker ishlayotganini DB orqali tasdiqlovchi singleton yozuv."""
    service = models.CharField(max_length=40, primary_key=True)
    seen_at = models.DateTimeField()
    details = models.JSONField(default=dict, blank=True)


class Announcement(models.Model):
    class Audience(models.TextChoices):
        ALL = "all", "Barcha ota-onalar"
        GROUP = "group", "Ma'lum guruh"
        DEBTORS = "debtors", "Faqat qarzdorlar"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    kindergarten = models.ForeignKey("school.Kindergarten", on_delete=models.CASCADE,
                                     related_name="announcements")
    title = models.CharField("Sarlavha", max_length=160)
    text = models.TextField("Xabar")
    send_at = models.DateTimeField("Yuborish vaqti")
    audience = models.CharField("Auditoriya", max_length=12,
                                choices=Audience.choices, default=Audience.ALL)
    group = models.ForeignKey("school.Group", verbose_name="Guruh", null=True, blank=True,
                              on_delete=models.SET_NULL, related_name="announcements")
    queued_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey("accounts.User", on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-send_at"]
