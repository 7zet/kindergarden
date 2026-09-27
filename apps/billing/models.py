import uuid
from decimal import Decimal

from django.db import models
from django.core.validators import MinValueValidator
from django.db.models import Sum
from django.db.models.functions import Coalesce


class LineKind(models.TextChoices):
    TUITION = "tuition", "Oylik to'lov"
    PRORATION = "proration", "Qisman oy"
    HOLD = "hold", "Joy saqlash"
    DISCOUNT = "discount", "Chegirma"
    MANUAL = "manual", "Qo'lda tuzatish"


class InvoiceStatus(models.TextChoices):
    ISSUED = "issued", "Chiqarilgan"
    PARTIAL = "partial", "Qisman to'langan"
    PAID = "paid", "To'langan"
    VOID = "void", "Bekor qilingan"


class InvoiceQuerySet(models.QuerySet):
    def with_balance(self):
        """Qoldiq ustun emas — har safar hisoblanadi. Yagona haqiqat manbai."""
        return self.annotate(
            paid_amount=Coalesce(
                Sum("allocations__amount"), Decimal("0"),
                output_field=models.DecimalField(max_digits=12, decimal_places=2),
            )
        )

    def unpaid(self):
        return (
            self.with_balance()
            .filter(paid_amount__lt=models.F("total_amount"))
            .exclude(status=InvoiceStatus.VOID)
        )


class Invoice(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    kindergarten = models.ForeignKey("school.Kindergarten", on_delete=models.PROTECT)
    enrollment = models.ForeignKey(
        "school.Enrollment", on_delete=models.PROTECT, related_name="invoices"
    )
    number = models.CharField(max_length=48)
    period = models.DateField(help_text="Oyning birinchi kuni")
    issued_at = models.DateField()
    due_at = models.DateField()
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(
        max_length=10, choices=InvoiceStatus.choices, default=InvoiceStatus.ISSUED
    )
    created_at = models.DateTimeField(auto_now_add=True)

    objects = InvoiceQuerySet.as_manager()

    class Meta:
        unique_together = [("enrollment", "period")]
        ordering = ["-period"]
        indexes = [models.Index(fields=["kindergarten", "period"])]
        constraints = [models.UniqueConstraint(
            fields=["kindergarten", "number"], name="uniq_invoice_number_per_tenant")]

    def __str__(self):
        return self.number

    @property
    def paid(self):
        return self.allocations.aggregate(s=Sum("amount"))["s"] or Decimal("0")

    @property
    def balance(self):
        return self.total_amount - self.paid

    def refresh_status(self, save=True):
        if self.status == InvoiceStatus.VOID:
            return self.status
        bal = self.balance
        if bal <= 0:
            self.status = InvoiceStatus.PAID
        elif bal < self.total_amount:
            self.status = InvoiceStatus.PARTIAL
        else:
            self.status = InvoiceStatus.ISSUED
        if save:
            self.save(update_fields=["status"])
        return self.status

    def recalc_total(self, save=True):
        self.total_amount = self.lines.aggregate(s=Sum("amount"))["s"] or Decimal("0")
        if save:
            self.save(update_fields=["total_amount"])
        return self.total_amount


class InvoiceLine(models.Model):
    """Summa shu yerda muzlatiladi — tarif keyin o'zgarsa ham o'zgarmaydi."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="lines")
    kind = models.CharField(max_length=12, choices=LineKind.choices)
    title = models.CharField(max_length=160)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    meta = models.JSONField(default=dict, blank=True)


class PaymentMethod(models.TextChoices):
    CASH = "cash", "Naqd"
    PAYME = "payme", "Payme"
    CLICK = "click", "Click"
    UZUM = "uzum", "Uzum"
    TRANSFER = "transfer", "Bank o'tkazmasi"


class Payment(models.Model):
    """Invoysga bevosita bog'lanmaydi — Allocation orqali, chunki bitta
    to'lov bir necha oyni yopishi mumkin."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    kindergarten = models.ForeignKey("school.Kindergarten", on_delete=models.PROTECT)
    child = models.ForeignKey(
        "school.Child", on_delete=models.PROTECT, null=True, blank=True,
        related_name="payments", verbose_name="Bola",
    )
    method = models.CharField(
        "To'lov usuli", max_length=10, choices=PaymentMethod.choices,
        default=PaymentMethod.CASH,
    )
    external_id = models.CharField(max_length=120, blank=True)
    amount = models.DecimalField(
        "Summa", max_digits=12, decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    received_at = models.DateTimeField("Qabul qilindi")
    is_reversed = models.BooleanField(default=False)
    note = models.CharField("Izoh", max_length=200, blank=True)
    created_by = models.ForeignKey(
        "accounts.User", on_delete=models.PROTECT, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-received_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["kindergarten", "method", "external_id"],
                condition=models.Q(external_id__gt=""),
                name="uniq_provider_txn_per_tenant",
            ),
            models.CheckConstraint(
                condition=models.Q(amount__gt=0), name="payment_amount_positive"
            ),
        ]

    @property
    def allocated(self):
        return self.allocations.aggregate(s=Sum("amount"))["s"] or Decimal("0")

    @property
    def unallocated(self):
        return self.amount - self.allocated


class Allocation(models.Model):
    """To'lovning bir qismi qaysi invoysga yozilgani.
    Avans — bu taqsimlanmagan qoldiq, alohida jadval kerak emas."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    payment = models.ForeignKey(
        Payment, on_delete=models.CASCADE, related_name="allocations"
    )
    invoice = models.ForeignKey(
        Invoice, on_delete=models.PROTECT, related_name="allocations"
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
