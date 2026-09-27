import uuid

from django.db import models


class Status(models.TextChoices):
    PRESENT = "present", "Keldi"
    ABSENT = "absent", "Kelmadi"


class Reason(models.TextChoices):
    SICK = "sick", "Kasal"
    FAMILY = "family", "Oilaviy"
    VACATION = "vacation", "Ta'til"
    UNEXCUSED = "unexcused", "Sababsiz"


class Attendance(models.Model):
    """Bir bola, bir kun, bir yozuv.

    Kech keldi  = present + arrived_at
    Erta ketdi  = present + left_at
    Sababli yo'q = absent + reason
    Tekshirilmagan = yozuv yo'q
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    enrollment = models.ForeignKey(
        "school.Enrollment", on_delete=models.CASCADE, related_name="attendance"
    )
    day = models.DateField()
    status = models.CharField(max_length=10, choices=Status.choices)
    reason = models.CharField(max_length=12, choices=Reason.choices, blank=True)
    arrived_at = models.TimeField(null=True, blank=True)
    left_at = models.TimeField(null=True, blank=True)
    has_document = models.BooleanField(default=False)
    note = models.CharField(max_length=200, blank=True)
    marked_by = models.ForeignKey(
        "accounts.User", on_delete=models.PROTECT, null=True, blank=True
    )
    marked_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("enrollment", "day")]
        indexes = [models.Index(fields=["enrollment", "day"])]

    def __str__(self):
        return f"{self.enrollment} {self.day} {self.status}"


class MonthLock(models.Model):
    """Oy yopilgach tarbiyachi davomatni o'zgartira olmaydi."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    group = models.ForeignKey(
        "school.Group", on_delete=models.CASCADE, related_name="month_locks"
    )
    period = models.DateField(help_text="Oyning birinchi kuni")
    locked_by = models.ForeignKey("accounts.User", on_delete=models.PROTECT, null=True)
    locked_at = models.DateTimeField(auto_now_add=True)
    reopened_at = models.DateTimeField(null=True, blank=True)
    reopen_note = models.TextField(blank=True)

    class Meta:
        unique_together = [("group", "period")]

    @property
    def is_locked(self):
        return self.reopened_at is None


class CheckEvent(models.Model):
    """Kirish-chiqishning o'chirilmaydigan operatsion jurnali."""

    class Kind(models.TextChoices):
        IN = "in", "Check-in"
        OUT = "out", "Check-out"

    class Method(models.TextChoices):
        QR = "qr", "QR"
        MANUAL = "manual", "Qo'lda"
        PARENT_PASS = "parent_pass", "Ota-ona QR"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    enrollment = models.ForeignKey(
        "school.Enrollment", on_delete=models.PROTECT, related_name="check_events"
    )
    kind = models.CharField(max_length=4, choices=Kind.choices)
    occurred_at = models.DateTimeField()
    method = models.CharField(max_length=12, choices=Method.choices)
    pickup_contact = models.ForeignKey(
        "school.Contact", on_delete=models.PROTECT, null=True, blank=True,
        related_name="pickup_events", verbose_name="Olib ketuvchi",
    )
    contact = models.ForeignKey(
        "school.Contact", on_delete=models.PROTECT, null=True, blank=True,
        related_name="check_events", verbose_name="Topshirgan/olib ketgan kontakt",
    )
    recorded_by = models.ForeignKey(
        "accounts.User", on_delete=models.PROTECT, related_name="check_events"
    )
    note = models.CharField(max_length=200, blank=True)
    idempotency_key = models.UUIDField(null=True, blank=True, unique=True)
    is_override = models.BooleanField(default=False)
    override_by = models.ForeignKey(
        "accounts.User", on_delete=models.PROTECT, null=True, blank=True,
        related_name="overridden_check_events",
    )
    override_reason = models.CharField(max_length=240, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    device_info = models.CharField(max_length=200, blank=True)
    synced_offline = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-occurred_at"]
        indexes = [models.Index(fields=["enrollment", "occurred_at"])]
        permissions = [
            ("check_in_child", "Bolani check-in qilish"),
            ("check_out_child", "Bolani check-out qilish"),
            ("manual_check_child", "Qo'lda check-in/out qilish"),
            ("override_check_child", "Ruxsatsiz check-outni tasdiqlash"),
        ]

    def delete(self, *args, **kwargs):
        raise PermissionError("Check-in/out tarixini o'chirib bo'lmaydi")
