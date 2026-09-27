import uuid
from decimal import Decimal

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from .phones import normalize_phone


class Kindergarten(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField("Nomi", max_length=160)
    address = models.CharField("Manzil", max_length=255, blank=True)
    phone = models.CharField("Telefon", max_length=20, blank=True)
    legal_name = models.CharField("Rasmiy nomi", max_length=255, blank=True)
    inn = models.CharField("STIR", max_length=20, blank=True)
    bank_name = models.CharField("Bank nomi", max_length=160, blank=True)
    bank_account = models.CharField("Hisob raqami", max_length=32, blank=True)
    bank_mfo = models.CharField("MFO", max_length=10, blank=True)
    director_name = models.CharField("Direktor F.I.O.", max_length=160, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class BillingPolicy(models.Model):
    """Barcha o'zgaruvchan moliyaviy qoidalar shu yerda."""

    class Proration(models.TextChoices):
        DAILY = "daily", "Kunlar bo'yicha"
        HALF = "half", "Yarim oy"
        FULL = "full", "To'liq oy"

    class AbsentMonth(models.TextChoices):
        FULL = "full", "To'liq olinadi"
        PERCENT = "percent", "Foiz bilan (joy saqlash)"
        NONE = "none", "Olinmaydi"

    kindergarten = models.OneToOneField(
        Kindergarten, on_delete=models.CASCADE, related_name="policy"
    )
    entry_proration = models.CharField(
        "Oy o'rtasida kirish", max_length=10,
        choices=Proration.choices, default=Proration.DAILY,
    )
    exit_proration = models.CharField(
        "Oy o'rtasida chiqish", max_length=10,
        choices=Proration.choices, default=Proration.DAILY,
    )
    absent_month_mode = models.CharField(
        "Butun oy kelmasa", max_length=10,
        choices=AbsentMonth.choices, default=AbsentMonth.FULL,
    )
    absent_month_percent = models.DecimalField(
        "Joy saqlash foizi", max_digits=5, decimal_places=2, default=Decimal("100.00"),
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    absent_month_threshold = models.PositiveSmallIntegerField(
        "Chegara (kun)", default=0,
        help_text="Necha kundan kam kelsa 'butun oy kelmadi' hisoblanadi.",
    )
    invoice_generation_day = models.PositiveSmallIntegerField(
        "Invoys chiqadigan kun", default=1,
        validators=[MinValueValidator(1), MaxValueValidator(28)],
    )
    due_day = models.PositiveSmallIntegerField(
        "To'lov muddati (kun)", default=10,
        validators=[MinValueValidator(1), MaxValueValidator(28)],
    )
    overpayment_as_advance = models.BooleanField("Ortiqcha to'lov avansda", default=True)
    rounding_step = models.PositiveIntegerField("Yaxlitlash qadami", default=100)
    currency = models.CharField("Valyuta", max_length=3, default="UZS")

    class Meta:
        verbose_name = "Moliyaviy siyosat"

    def __str__(self):
        return f"{self.kindergarten.name} siyosati"


class WorkingCalendar(models.Model):
    """Ish kunlari. Bayramlar har yili siljiydi, shuning uchun bazada."""

    kindergarten = models.ForeignKey(
        Kindergarten, on_delete=models.CASCADE, related_name="calendar_days"
    )
    day = models.DateField()
    is_working = models.BooleanField(default=True)
    note = models.CharField(max_length=120, blank=True)

    class Meta:
        unique_together = [("kindergarten", "day")]
        indexes = [models.Index(fields=["kindergarten", "day"])]
        ordering = ["day"]


class Tariff(models.Model):
    """Versiyalanadi — tahrirlanmaydi, yangi qator qo'shiladi."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    kindergarten = models.ForeignKey(
        Kindergarten, on_delete=models.CASCADE, related_name="tariffs"
    )
    name = models.CharField("Nomi", max_length=80)
    monthly_amount = models.DecimalField("Oylik summa", max_digits=12, decimal_places=2)
    valid_from = models.DateField("Amal qiladi")
    valid_to = models.DateField("Tugaydi", null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-valid_from", "name"]

    def __str__(self):
        return f"{self.name} — {self.monthly_amount:,.0f}".replace(",", " ")


class Discount(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    kindergarten = models.ForeignKey(
        Kindergarten, on_delete=models.CASCADE, related_name="discounts"
    )
    name = models.CharField("Nomi", max_length=80)
    percent = models.DecimalField(
        "Foiz", max_digits=5, decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} ({self.percent}%)"

class Group(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    kindergarten = models.ForeignKey(
        Kindergarten, on_delete=models.CASCADE, related_name="groups"
    )
    name = models.CharField("Nomi", max_length=80)
    age_from = models.PositiveSmallIntegerField("Yosh (dan)", null=True, blank=True)
    age_to = models.PositiveSmallIntegerField("Yosh (gacha)", null=True, blank=True)
    capacity = models.PositiveSmallIntegerField("Sig'im", default=25)
    max_ratio = models.PositiveSmallIntegerField(
        "Maksimal nisbat (bola : tarbiyachi)", default=0,
        help_text="0 = tekshirilmaydi. Masalan 10 = bitta tarbiyachiga "
                  "10 tadan ko'p bola bo'lmasligi kerak.",
    )
    default_tariff = models.ForeignKey(
        Tariff, on_delete=models.PROTECT, null=True, blank=True,
        verbose_name="Standart tarif",
    )
    teachers = models.ManyToManyField(
        "accounts.User", blank=True, related_name="taught_groups",
        verbose_name="Tarbiyachilar",
        help_text="Tarbiyachi va yordamchi. Faqat shu ro'yxatdagilar "
                  "guruh davomatini belgilay oladi.",
    )

    class Language(models.TextChoices):
        UZ = "uz", "O'zbek"
        RU = "ru", "Rus"
        EN = "en", "Ingliz"
        MIXED = "mixed", "Aralash"

    lead_teacher = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="lead_groups", verbose_name="Asosiy tarbiyachi",
        help_text="Tarbiyachilar ro'yxatidan bittasi. Hisobot va "
                  "mas'uliyat uchun.",
    )
    language = models.CharField(
        "Ta'lim tili", max_length=6, choices=Language.choices,
        default=Language.UZ,
    )
    room_number = models.CharField("Xona raqami", max_length=20, blank=True)
    opens_at = models.TimeField("Ish boshlanishi", null=True, blank=True)
    closes_at = models.TimeField("Ish tugashi", null=True, blank=True)


    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        permissions = [("view_all_groups", "Barcha guruhlarni ko'rish")]
        constraints = [
            models.CheckConstraint(
                condition=(models.Q(age_from__isnull=True) |
                           models.Q(age_to__isnull=True) |
                           models.Q(age_from__lte=models.F("age_to"))),
                name="group_valid_age_range",
            )
        ]

    def clean(self):
        super().clean()
        if (self.age_from is not None and self.age_to is not None and
                self.age_from > self.age_to):
            from django.core.exceptions import ValidationError
            raise ValidationError({
                "age_to": "Yosh (gacha) qiymati yosh (dan) qiymatidan kichik bo'lmasligi kerak."
            })

    def __str__(self):
        return self.name

    @property
    def active_count(self):
        """Hozir kelayotgan bolalar: boshlangan, to'xtatilmagan, tugamagan."""
        return self.enrollments.effective_on().filter(is_paused=False).count()

    @property
    def reserved_count(self):
        """Qabul qilingan, lekin hali boshlamagan — joy band."""
        return self.enrollments.open_on().filter(
            started_at__gt=timezone.localdate()).count()

    @property
    def present_today(self):
        """Bugun kelgan bolalar soni."""
        from apps.attendance.models import Attendance, Status
        return Attendance.objects.filter(
            enrollment__group=self, day=timezone.localdate(),
            status=Status.PRESENT).count()

    @property
    def occupancy(self):
        """Joylashuv holati: sig'imga nisbatan (band joylar rezervni ham hisoblaydi)."""
        taken = self.active_count + self.reserved_count
        if taken > self.capacity:
            return "over"
        if taken == self.capacity:
            return "full"
        return "open"

    @property
    def occupancy_display(self):
        return {"open": "Joy mavjud", "full": "To'liq",
                "over": "Sig'imdan oshgan"}[self.occupancy]

    @property
    def teacher_names(self):
        return ", ".join(t.full_name for t in self.teachers.all()) or "—"

    @property
    def working_hours(self):
        if self.opens_at and self.closes_at:
            return f"{self.opens_at:%H:%M} – {self.closes_at:%H:%M}"
        return "—"

    @property
    def assistant_names(self):
        """Asosiy tarbiyachidan boshqa xodimlar."""
        others = [t.full_name for t in self.teachers.all()
                  if t.pk != self.lead_teacher_id]
        return ", ".join(others) or "—"

    @property
    def staff_count(self):
        return self.teachers.count()

    @property
    def ratio(self):
        """Bola : tarbiyachi. Tarbiyachi yo'q bo'lsa None."""
        staff = self.staff_count
        if not staff:
            return None
        return round(self.active_count / staff, 1)

    @property
    def ratio_display(self):
        r = self.ratio
        return f"{r}:1" if r is not None else "—"

    @property
    def ratio_exceeded(self):
        return bool(self.max_ratio) and self.ratio is not None \
            and self.ratio > self.max_ratio



class Child(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    kindergarten = models.ForeignKey(
        Kindergarten, on_delete=models.CASCADE, related_name="children"
    )
    full_name = models.CharField("F.I.O.", max_length=160)
    birth_date = models.DateField("Tug'ilgan sana")

    class Gender(models.TextChoices):
        MALE = "m", "O'g'il"
        FEMALE = "f", "Qiz"

    code = models.CharField(
        "ID raqami", max_length=20, blank=True, db_index=True,
        help_text="Bo'sh qoldirilsa avtomatik beriladi.")
    gender = models.CharField(
        "Jinsi", max_length=1, choices=Gender.choices, blank=True)
    allergies = models.CharField(
        "Allergiya", max_length=200, blank=True,
        help_text="Bola kartasida qizil ogohlantirish sifatida ko'rinadi.")
    health_note = models.TextField(
        "Sog'liq haqida", blank=True,
        help_text="Surunkali kasallik, doimiy dori, cheklovlar.")
    address = models.CharField("Manzil", max_length=255, blank=True)
    doctor_name = models.CharField("Shifokor", max_length=160, blank=True)
    doctor_phone = models.CharField("Shifokor telefoni", max_length=20, blank=True)
    note = models.TextField("Izoh", blank=True)
    is_archived = models.BooleanField("Arxivda", default=False)
    check_token = models.UUIDField(
        "Check-in QR tokeni", default=uuid.uuid4, unique=True, editable=False
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["full_name"]
        verbose_name_plural = "Bolalar"

    def __str__(self):
        return self.full_name

    @property
    def current_enrollment(self):
        today = timezone.localdate()
        current = self.enrollments.effective_on(today).first()
        if current:
            return current
        return self.enrollments.open_on(today).filter(
            started_at__gt=today).order_by("started_at").first()

    @property
    def primary_contact(self):
        return self.contacts.filter(is_primary=True).first() or self.contacts.first()

    @property
    def payer(self):
        return self.contacts.filter(is_payer=True).first() or self.primary_contact

    @property
    def parent_phone(self):
        return self.primary_contact.phone if self.primary_contact else ""

    @property
    def parent_name(self):
        return self.primary_contact.full_name if self.primary_contact else ""

    @property
    def pickup_contacts(self):
        return self.contacts.filter(can_pickup=True)

    @property
    def age_months(self):
        today = timezone.localdate()
        return (today.year - self.birth_date.year) * 12 + \
            today.month - self.birth_date.month - \
            (1 if today.day < self.birth_date.day else 0)

    @property
    def age(self):
        return self.age_months // 12

    @property
    def age_display(self):
        years, months = divmod(self.age_months, 12)
        if years == 0:
            return f"{months} oylik"
        return f"{years} yosh {months} oy" if months else f"{years} yosh"

    @property
    def has_warning(self):
        return bool(self.allergies or self.health_note)


class Person(models.Model):
    """Bog'cha ichidagi haqiqiy jismoniy shaxs; telefon identifikator emas."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    kindergarten = models.ForeignKey(
        Kindergarten, on_delete=models.CASCADE, related_name="persons")
    full_name = models.CharField("F.I.O.", max_length=160)
    phone = models.CharField("Telefon", max_length=20, blank=True)
    normalized_phone = models.CharField(max_length=20, blank=True, db_index=True,
                                        editable=False)
    note = models.CharField("Shaxs haqida izoh", max_length=200, blank=True)
    is_active = models.BooleanField("Faol", default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["full_name"]
        indexes = [models.Index(fields=["kindergarten", "normalized_phone"],
                                name="school_pers_kinderg_9c8618_idx")]

    def save(self, *args, **kwargs):
        self.normalized_phone = normalize_phone(self.phone)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.full_name


def child_document_path(instance, filename):
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "bin"
    return f"private/{instance.kindergarten_id}/{instance.child_id}/{uuid.uuid4().hex}.{ext}"


class ChildDocument(models.Model):
    class Type(models.TextChoices):
        CONTRACT = "contract", "Shartnoma skani"
        BIRTH = "birth", "Tug'ilganlik guvohnomasi"
        MEDICAL = "medical", "Tibbiy ma'lumotnoma"
        PICKUP = "pickup", "Olib ketish ruxsati"
        OTHER = "other", "Boshqa"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    kindergarten = models.ForeignKey(Kindergarten, on_delete=models.CASCADE,
                                     related_name="child_documents")
    child = models.ForeignKey(Child, on_delete=models.CASCADE, related_name="documents")
    type = models.CharField(max_length=12, choices=Type.choices)
    title = models.CharField(max_length=160)
    file = models.FileField(upload_to=child_document_path)
    valid_until = models.DateField(null=True, blank=True)
    uploaded_by = models.ForeignKey("accounts.User", on_delete=models.PROTECT)
    is_archived = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if self.child.kindergarten_id != self.kindergarten_id:
            raise ValueError("Hujjat va bola bitta bog'chaga tegishli bo'lishi kerak")
        super().save(*args, **kwargs)


class ContactManager(models.Manager):
    """Eski create API'ni xavfsiz saqlaydi; identity Person'ga yoziladi."""
    def create(self, **kwargs):
        full_name = kwargs.pop("full_name", None)
        phone = kwargs.pop("phone", None)
        if not kwargs.get("person"):
            child = kwargs.get("child")
            if child is None and kwargs.get("child_id"):
                child = Child.objects.get(pk=kwargs["child_id"])
            kwargs["person"] = Person.objects.create(
                kindergarten=child.kindergarten, full_name=full_name or "Kontakt",
                phone=phone or "")
        return super().create(**kwargs)

    def get_or_create(self, defaults=None, **kwargs):
        defaults = dict(defaults or {})
        phone = kwargs.pop("phone", None)
        full_name = defaults.pop("full_name", None) or kwargs.pop("full_name", None)
        if "person" not in kwargs and phone is not None:
            child = kwargs.get("child")
            normalized = normalize_phone(phone)
            person = Person.objects.filter(
                kindergarten=child.kindergarten, normalized_phone=normalized,
                full_name__iexact=full_name or "").first()
            if not person:
                person = Person.objects.create(kindergarten=child.kindergarten,
                                               full_name=full_name or "Kontakt", phone=phone)
            kwargs["person"] = person
        return super().get_or_create(defaults=defaults, **kwargs)


class Contact(models.Model):
    """Person va bola o'rtasidagi aloqa hamda aynan shu bolaga tegishli ruxsatlar."""
    class Kind(models.TextChoices):
        PARENT = "parent", "Ota-ona"
        FAMILY = "family", "Qarindosh"
        PICKUP = "pickup", "Olib ketuvchi"
        EMERGENCY = "emergency", "Favqulodda"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    child = models.ForeignKey(Child, on_delete=models.CASCADE, related_name="contacts")
    person = models.ForeignKey(Person, on_delete=models.CASCADE, related_name="contacts")
    relation = models.CharField("Kimligi", max_length=60)
    kind = models.CharField("Turi", max_length=10, choices=Kind.choices)
    is_primary = models.BooleanField("Asosiy aloqa", default=False)
    is_payer = models.BooleanField("To'lovchi", default=False)
    can_pickup = models.BooleanField("Olib ketishi mumkin", default=False)
    has_app_access = models.BooleanField("Kabinetga kirish", default=False)
    can_see_billing = models.BooleanField("Moliyani ko'rish", default=False)
    receives_messages = models.BooleanField("Xabar oladi", default=True)
    note = models.CharField("Izoh", max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    notify_attendance = models.BooleanField("Davomat xabarlari", default=True)
    notify_billing = models.BooleanField("Moliya xabarlari", default=True)

    class Meta:
        ordering = ["-is_primary", "kind", "person__full_name"]
        indexes = [models.Index(fields=["child", "kind"])]
        constraints = [models.UniqueConstraint(fields=["person", "child"],
                                                name="unique_person_child_contact")]

    objects = ContactManager()

    @property
    def full_name(self):
        return self.person.full_name

    @property
    def phone(self):
        return self.person.phone

    def __str__(self):
        return f"{self.full_name} ({self.child.full_name})"

    def save(self, *args, **kwargs):
        if self.person.kindergarten_id != self.child.kindergarten_id:
            raise ValueError("Person va bola bitta bog'chaga tegishli bo'lishi kerak")
        if self.is_primary:
            Contact.objects.filter(child=self.child, is_primary=True).exclude(
                pk=self.pk).update(is_primary=False)
        if self.is_payer:
            Contact.objects.filter(child=self.child, is_payer=True).exclude(
                pk=self.pk).update(is_payer=False)
        super().save(*args, **kwargs)


class ContactChild(Contact):
    """Yangi kod uchun aniq nom; Contact eski importlar bilan mos proxy."""
    class Meta:
        proxy = True
        verbose_name = "Bola kontakti"
        verbose_name_plural = "Bola kontaktlari"


class TelegramAccount(models.Model):
    telegram_user_id = models.BigIntegerField(unique=True)
    chat_id = models.BigIntegerField()
    persons = models.ManyToManyField(Person, related_name="telegram_accounts", blank=True)
    language = models.CharField(max_length=2, default="uz")
    linked_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)


class TelegramLinkCode(models.Model):
    token = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    contact = models.ForeignKey(Contact, on_delete=models.CASCADE, related_name="telegram_codes")
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey("accounts.User", on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def is_valid(self):
        return self.used_at is None and self.expires_at > timezone.now()


class PickupPass(models.Model):
    token = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    child = models.ForeignKey(Child, on_delete=models.CASCADE, related_name="pickup_passes")
    contact = models.ForeignKey(Contact, on_delete=models.CASCADE, related_name="pickup_passes")
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def is_valid(self):
        return self.used_at is None and self.expires_at > timezone.now()


class ContactPass(models.Model):
    """Bitta jismoniy kontaktga tegishli qisqa muddatli QR/kod."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    person = models.ForeignKey(Person, on_delete=models.CASCADE, related_name="contact_passes")
    code = models.CharField(max_length=6, db_index=True)
    qr_expires_at = models.DateTimeField()
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def is_valid(self):
        return self.used_at is None and self.expires_at > timezone.now()


class StaffTelegramAccount(models.Model):
    user = models.OneToOneField(
        "accounts.User", on_delete=models.CASCADE, related_name="staff_telegram"
    )
    telegram_user_id = models.BigIntegerField(unique=True)
    chat_id = models.BigIntegerField()
    linked_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)


class StaffTelegramLinkCode(models.Model):
    token = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        "accounts.User", on_delete=models.PROTECT, related_name="created_staff_link_codes"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def is_valid(self):
        return self.used_at is None and self.expires_at > timezone.now()

class EnrollmentQuerySet(models.QuerySet):
    def effective_on(self, day=None):
        """Berilgan kunda shartnomasi kuchda bo'lgan yozuvlar."""
        day = day or timezone.localdate()
        return self.filter(started_at__lte=day).filter(
            models.Q(ended_at__isnull=True) | models.Q(ended_at__gte=day)
        )

    def open_on(self, day=None):
        """Tugamagan shartnomalar: faol, pauza yoki kelajak rezervi."""
        day = day or timezone.localdate()
        return self.filter(
            models.Q(ended_at__isnull=True) | models.Q(ended_at__gte=day)
        )


class Enrollment(models.Model):
    """Shartnoma. Guruh yoki tarif o'zgarsa — eskisi yopilib, yangisi ochiladi."""

    class EndReason(models.TextChoices):
        GRADUATED = "graduated", "Bitirdi"
        LEFT = "left", "Ketdi"
        TRANSFERRED = "transferred", "Boshqa bog'chaga o'tdi"
        EXPELLED = "expelled", "Chiqarildi"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    child = models.ForeignKey(Child, on_delete=models.PROTECT, related_name="enrollments")
    group = models.ForeignKey(
        Group, on_delete=models.PROTECT, related_name="enrollments",
        verbose_name="Guruh")
    tariff = models.ForeignKey(Tariff, on_delete=models.PROTECT, verbose_name="Tarif")
    discount = models.ForeignKey(
        Discount, on_delete=models.PROTECT, null=True, blank=True,
        verbose_name="Chegirma",
    )
    started_at = models.DateField("Boshlanish")
    ended_at = models.DateField("Tugash", null=True, blank=True)

    is_paused = models.BooleanField(
        "Vaqtincha to'xtatilgan", default=False,
        help_text="Yoqilgan bo'lsa invoys chiqmaydi. Joy saqlanadi.")
    pause_note = models.CharField("To'xtatish sababi", max_length=200, blank=True)
    end_reason = models.CharField(
        "Tugash sababi", max_length=12, choices=EndReason.choices, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    objects = EnrollmentQuerySet.as_manager()

    class Meta:
        ordering = ["-started_at"]
        indexes = [models.Index(fields=["group", "ended_at"])]

    @property
    def status(self):
        """Sanalar va bayroqlardan hosil bo'ladi — alohida maydon emas.
        Shuning uchun 'status=ended, lekin ended_at bo'sh' holati mumkin emas."""
        today = timezone.localdate()
        if self.ended_at is not None and self.ended_at < today:
            return "ended"
        if self.is_paused:
            return "paused"
        if self.started_at > today:
            return "enrolled"
        return "active"

    @property
    def status_display(self):
        if self.status == "ended":
            return self.get_end_reason_display() or "Tugagan"
        return {
            "enrolled": "Qabul qilingan",
            "active": "Faol",
            "paused": "To'xtatilgan",
        }[self.status]

    @property
    def is_active(self):
        """Bola hozir kelayapti: boshlangan, to'xtatilmagan, tugamagan."""
        return self.status == "active"

    @property
    def is_open(self):
        """Shartnoma amal qilmoqda — hali boshlanmagan bo'lsa ham.
        Guruhga biriktirish va joy hisobida shu ishlatiladi."""
        return self.ended_at is None or self.ended_at >= timezone.localdate()

    def clean(self):
        super().clean()
        from django.core.exceptions import ValidationError
        errors = {}
        if self.ended_at and self.ended_at < self.started_at:
            errors["ended_at"] = "Tugash sanasi boshlanish sanasidan oldin bo'lishi mumkin emas."
        if self.child_id and self.group_id and self.child.kindergarten_id != self.group.kindergarten_id:
            errors["group"] = "Bola va guruh bitta bog'chaga tegishli bo'lishi kerak."
        if self.child_id and self.tariff_id and self.child.kindergarten_id != self.tariff.kindergarten_id:
            errors["tariff"] = "Bola va tarif bitta bog'chaga tegishli bo'lishi kerak."
        if self.child_id and self.discount_id and self.child.kindergarten_id != self.discount.kindergarten_id:
            errors["discount"] = "Bola va chegirma bitta bog'chaga tegishli bo'lishi kerak."
        if errors:
            raise ValidationError(errors)

    @property
    def age(self):
        today = timezone.localdate()
        return today.year - self.birth_date.year - (
                (today.month, today.day) < (self.birth_date.month, self.birth_date.day))

    @property
    def age_months(self):
        today = timezone.localdate()
        return (today.year - self.birth_date.year) * 12 + \
            today.month - self.birth_date.month - \
            (1 if today.day < self.birth_date.day else 0)

    @property
    def age(self):
        return self.age_months // 12

    @property
    def age_display(self):
        y, m = divmod(self.age_months, 12)
        if y == 0:
            return f"{m} oylik"
        return f"{y} yosh {m} oy" if m else f"{y} yosh"

class Application(models.Model):
    """Qabulgacha bo'lgan voronka. Bu yerda pul yo'q — guruh, tarif va
    sana majburiy emas. Qabul qilinganda Child + Enrollment yaratiladi."""

    class Status(models.TextChoices):
        INQUIRY = "inquiry", "So'rov"
        TOURED = "toured", "Tanishuvga keldi"
        APPLIED = "applied", "Ariza topshirdi"
        WAITLIST = "waitlist", "Navbatda"
        ACCEPTED = "accepted", "Qabul qilindi"
        DECLINED = "declined", "Rad etildi"
        LOST = "lost", "Boshqa joyni tanladi"

    OPEN_STATUSES = ["inquiry", "toured", "applied", "waitlist"]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    kindergarten = models.ForeignKey(
        Kindergarten, on_delete=models.CASCADE, related_name="applications")
    child_name = models.CharField("Bola F.I.O.", max_length=160)
    birth_date = models.DateField("Tug'ilgan sana", null=True, blank=True)
    parent_name = models.CharField("Ota-ona", max_length=160)
    parent_phone = models.CharField("Telefon", max_length=20)
    desired_group = models.ForeignKey(
        Group, on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name="Istalgan guruh")
    desired_start = models.DateField("Boshlash sanasi", null=True, blank=True)
    status = models.CharField(
        "Holat", max_length=10, choices=Status.choices, default=Status.INQUIRY)
    source = models.CharField(
        "Qayerdan bilgan", max_length=80, blank=True,
        help_text="Tavsiya, Instagram, yon ko'chadan va h.k.")
    note = models.TextField("Izoh", blank=True)
    child = models.ForeignKey(
        Child, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="applications",
        help_text="Qabul qilingandan keyin to'ldiriladi.")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["kindergarten", "status"])]

    @property
    def is_open(self):
        return self.status in self.OPEN_STATUSES

    def __str__(self):
        return f"{self.child_name} ({self.get_status_display()})"
