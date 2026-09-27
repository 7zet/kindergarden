from django import forms
from django.contrib.auth import password_validation
from django.core.validators import MinValueValidator
from decimal import Decimal

from apps.accounts.models import Role, User
from apps.billing.models import Payment

from apps.school.models import (Application, BillingPolicy, Child, Contact, Discount,
                                Enrollment, Group, Kindergarten, Person, Tariff,
                                ChildDocument)






class BaseForm(forms.ModelForm):
    money_field_names = {
        "amount", "monthly_amount", "monthly_salary", "base_salary",
        "advance", "bonus", "penalty", "opening_balance", "actual_balance",
    }

    def __init__(self, *args, **kwargs):
        # Brauzerda 1,000,000.50 ko'rinishida yuborilgan pulni DecimalField
        # tushunadigan 1000000.50 formatiga o'tkazamiz. Nuqta kasr ajratgichi.
        if args and args[0] is not None:
            data = args[0].copy()
            for name in self.money_field_names:
                raw = data.get(name)
                if isinstance(raw, str):
                    data[name] = raw.replace(",", "").replace(" ", "")
            args = (data, *args[1:])
        super().__init__(*args, **kwargs)
        for name, f in self.fields.items():
            if isinstance(f.widget, (forms.CheckboxSelectMultiple,
                                     forms.RadioSelect)):
                continue
            css = "input"
            if isinstance(f.widget, forms.CheckboxInput):
                css = "checkbox"
            elif isinstance(f.widget, forms.Select):
                css = "input select"
            f.widget.attrs.setdefault("class", css)
            if name in self.money_field_names and isinstance(f, forms.DecimalField):
                # type=number vergul bilan guruhlangan qiymatni ko'rsata olmaydi.
                f.widget = forms.TextInput(attrs={
                    **f.widget.attrs,
                    "class": f.widget.attrs.get("class", "input"),
                    "inputmode": "decimal",
                    "autocomplete": "off",
                    "data-money": "true",
                    "placeholder": "0",
                })
            if isinstance(f.widget, forms.DateInput):
                f.widget.input_type = "date"


class ContactForm(BaseForm):
    existing_person = forms.ModelChoiceField(
        label="Mavjud shaxs", queryset=Person.objects.none(), required=False,
        help_text="Bu odam avval boshqa bolaga qo'shilgan bo'lsa tanlang.")
    full_name = forms.CharField(label="F.I.O.", max_length=160, required=False)
    phone = forms.CharField(label="Telefon", max_length=20, required=False)

    class Meta:
        model = Contact
        fields = ["existing_person", "full_name", "phone", "relation", "kind", "is_primary",
                  "is_payer", "can_pickup", "has_app_access",
                  "can_see_billing", "receives_messages", "note"]

    def __init__(self, *args, kindergarten=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.kindergarten = kindergarten
        self.fields["existing_person"].queryset = Person.objects.filter(
            kindergarten=kindergarten, is_active=True)
        person_id = getattr(self.instance, "person_id", None)
        person = Person.objects.filter(pk=person_id).first() if person_id else None
        if person:
            self.fields["existing_person"].initial = person
            self.fields["full_name"].initial = person.full_name
            self.fields["phone"].initial = person.phone

    def save(self, commit=True):
        contact = super().save(commit=False)
        person = self.cleaned_data.get("existing_person")
        if person is None:
            person = contact.person if contact.person_id else None
        if person is None:
            person = Person(kindergarten=self.kindergarten)
        if self.cleaned_data.get("full_name"):
            person.full_name = self.cleaned_data["full_name"]
        if self.cleaned_data.get("phone") or not person.pk:
            person.phone = self.cleaned_data.get("phone", "")
        if commit:
            person.save()
        contact.person = person
        if commit:
            contact.save()
            self.save_m2m()
        return contact

    def clean(self):
        data = super().clean()
        if not data.get("existing_person") and not data.get("full_name"):
            self.add_error("full_name", "Yangi shaxs uchun F.I.O. majburiy")
        person = data.get("existing_person")
        child = getattr(self.instance, "child", None)
        if (person and child and Contact.objects.filter(person=person, child=child)
                .exclude(pk=self.instance.pk).exists()):
            self.add_error("existing_person", "Bu shaxs ushbu bolaga allaqachon bog'langan.")
        return data


class ChildForm(BaseForm):
    class Meta:
        model = Child
        fields = ["full_name", "birth_date", "gender", "code", "address",
                  "doctor_name", "doctor_phone",
                  "allergies", "health_note", "note"]
        widgets = {"birth_date": forms.DateInput(),
                   "health_note": forms.Textarea({"rows": 2}),
                   "note": forms.Textarea({"rows": 2})}


class ChildDocumentForm(BaseForm):
    class Meta:
        model = ChildDocument
        fields = ["type", "title", "file", "valid_until"]
        widgets = {"valid_until": forms.DateInput(attrs={"type": "date"})}

    def clean_file(self):
        f = self.cleaned_data["file"]
        if f.size > 10 * 1024 * 1024:
            raise forms.ValidationError("Fayl 10 MB dan katta bo'lmasligi kerak")
        head = f.read(12); f.seek(0)
        allowed = (head.startswith(b"%PDF-"), head.startswith(b"\xff\xd8\xff"),
                   head.startswith(b"\x89PNG\r\n\x1a\n"))
        if not any(allowed):
            raise forms.ValidationError("Faqat haqiqiy PDF, JPEG yoki PNG fayl qabul qilinadi")
        return f


class GroupForm(BaseForm):
    class Meta:
        model = Group
        fields = ["name", "age_from", "age_to", "capacity", "max_ratio", "default_tariff",
                  "language", "room_number", "opens_at", "closes_at",
                  "teachers", "lead_teacher", "is_active"]
        widgets = {
            "teachers": forms.CheckboxSelectMultiple(),
            "opens_at": forms.TimeInput(attrs={"type": "time"}),
            "closes_at": forms.TimeInput(attrs={"type": "time"}),
        }

    def clean(self):
        data = super().clean()
        lead = data.get("lead_teacher")
        teachers = data.get("teachers")
        if lead and teachers is not None and lead not in teachers:
            # Asosiy tarbiyachini ikkinchi marta checkboxdan belgilash shart emas.
            data["teachers"] = teachers | User.objects.filter(pk=lead.pk)
        return data


class EnrollmentForm(BaseForm):
    allow_age_mismatch = forms.BooleanField(
        required=False,
        label="Yosh oralig'i mos kelmasa ham biriktirish",
        help_text="Faqat direktor tasdiqlagan istisno holatda belgilang.",
    )

    def __init__(self, *args, child=None, **kwargs):
        self.child = child
        super().__init__(*args, **kwargs)

    class Meta:
        model = Enrollment
        fields = ["group", "tariff", "discount", "started_at", "ended_at"]
        widgets = {"started_at": forms.DateInput(), "ended_at": forms.DateInput()}

    def clean(self):
        data = super().clean()
        child = self.child or getattr(self.instance, "child", None)
        group, started_at = data.get("group"), data.get("started_at")
        if child and group and started_at and not data.get("allow_age_mismatch"):
            age = started_at.year - child.birth_date.year - (
                (started_at.month, started_at.day) <
                (child.birth_date.month, child.birth_date.day)
            )
            if age < group.age_from or age > group.age_to:
                self.add_error(
                    "group",
                    f"Bola shartnoma boshlanishida {age} yosh bo'ladi, guruh esa "
                    f"{group.age_from}–{group.age_to} yosh uchun. Istisno bo'lsa "
                    "tasdiqlash belgisini qo'ying.",
                )
        return data


class TransferEnrollmentForm(BaseForm):
    effective_date = forms.DateField(label="Ko'chirish sanasi",
                                     widget=forms.DateInput(attrs={"type": "date"}))
    allow_age_mismatch = forms.BooleanField(
        required=False, label="Yosh oralig'i mos kelmasa ham ko'chirish",
        help_text="Faqat direktor tasdiqlagan istisno holatda belgilang.")

    def __init__(self, *args, child=None, **kwargs):
        self.child = child
        super().__init__(*args, **kwargs)

    class Meta:
        model = Enrollment
        fields = ["group", "tariff", "discount"]

    def clean(self):
        data = super().clean()
        child = self.child
        group, day = data.get("group"), data.get("effective_date")
        if child and group and day and not data.get("allow_age_mismatch"):
            age = day.year - child.birth_date.year - (
                (day.month, day.day) < (child.birth_date.month, child.birth_date.day))
            if age < group.age_from or age > group.age_to:
                self.add_error("group", f"Bola ko'chirish sanasida {age} yosh, "
                               f"guruh esa {group.age_from}–{group.age_to} yosh uchun.")
        return data


class TariffForm(BaseForm):
    class Meta:
        model = Tariff
        fields = ["name", "monthly_amount", "valid_from", "valid_to", "is_active"]
        widgets = {"valid_from": forms.DateInput(), "valid_to": forms.DateInput()}


class DiscountForm(BaseForm):
    class Meta:
        model = Discount
        fields = ["name", "percent", "is_active"]


class PolicyForm(BaseForm):
    class Meta:
        model = BillingPolicy
        exclude = ["kindergarten"]


class KindergartenDetailsForm(BaseForm):
    class Meta:
        model = Kindergarten
        fields = ["name", "legal_name", "address", "phone", "inn", "bank_name",
                  "bank_account", "bank_mfo", "director_name"]


class PaymentForm(BaseForm):
    class Meta:
        model = Payment
        fields = ["child", "amount", "method", "received_at", "note"]
        widgets = {"received_at": forms.DateTimeInput(attrs={"type": "datetime-local"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["amount"].validators.append(MinValueValidator(Decimal("0.01")))
        self.fields["amount"].widget.attrs.update({"min": "0.01", "step": "0.01"})


class UserForm(BaseForm):
    password = forms.CharField(
        label="Parol", widget=forms.PasswordInput(attrs={"class": "input"}),
        required=True, min_length=8,
        help_text="Kamida 8 belgi. Foydalanuvchi birinchi kirishda uni almashtiradi.")

    class Meta:
        model = User
        fields = ["full_name", "phone", "role", "is_active"]
        labels = {"role": "Rol", "is_active": "Faol"}
        help_texts = {
            "is_active": "O'chirilsa, foydalanuvchi tizimga kira olmaydi. Hisobni o'chirish o'rniga shundan foydalaning."
        }

    def clean_password(self):
        value = self.cleaned_data["password"]
        password_validation.validate_password(value)
        return value


class UserEditForm(BaseForm):
    class Meta:
        model = User
        fields = ["full_name", "phone", "role", "is_active"]
        labels = {"role": "Rol", "is_active": "Faol"}
        help_texts = {
            "is_active": "O'chirilsa foydalanuvchi tizimga kira olmaydi.",
        }


class AdminPasswordResetForm(forms.Form):
    password = forms.CharField(
        label="Yangi vaqtinchalik parol", min_length=8,
        widget=forms.PasswordInput(attrs={"class": "input", "autocomplete": "new-password"}),
    )
    password_confirm = forms.CharField(
        label="Parolni takrorlang", min_length=8,
        widget=forms.PasswordInput(attrs={"class": "input", "autocomplete": "new-password"}),
    )
    require_change = forms.BooleanField(
        label="Keyingi kirishda parolni almashtirishni talab qilish", required=False,
        initial=True,
    )

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("password") != cleaned.get("password_confirm"):
            raise forms.ValidationError("Parollar bir xil emas.")
        if cleaned.get("password"):
            password_validation.validate_password(cleaned["password"])
        return cleaned


class OwnPasswordChangeForm(AdminPasswordResetForm):
    old_password = forms.CharField(
        label="Joriy parol",
        widget=forms.PasswordInput(attrs={"class": "input", "autocomplete": "current-password"}),
    )
    require_change = None

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        self.fields.pop("require_change", None)

    def clean_old_password(self):
        value = self.cleaned_data["old_password"]
        if not self.user.check_password(value):
            raise forms.ValidationError("Joriy parol noto'g'ri.")
        return value


class RoleForm(BaseForm):
    class Meta:
        model = Role
        fields = ["name", "permissions"]
        widgets = {"permissions": forms.SelectMultiple(attrs={"size": 12})}


class ApplicationForm(BaseForm):
    class Meta:
        model = Application
        fields = ["child_name", "birth_date", "parent_name", "parent_phone",
                  "desired_group", "desired_start", "status", "source", "note"]
        widgets = {"birth_date": forms.DateInput(),
                   "desired_start": forms.DateInput(),
                   "note": forms.Textarea({"rows": 2})}


class AcceptForm(BaseForm):
    class Meta:
        model = Enrollment
        fields = ["group", "tariff", "discount", "started_at"]
        widgets = {"started_at": forms.DateInput()}


class EndEnrollmentForm(BaseForm):
    class Meta:
        model = Enrollment
        fields = ["ended_at", "end_reason"]
        widgets = {"ended_at": forms.DateInput()}
