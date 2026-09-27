from decimal import Decimal

from django import forms
from django.core.validators import MinValueValidator
from django.utils import timezone

from apps.accounts.models import User
from apps.school.models import Group
from apps.web.forms import BaseForm

from .models import (Announcement, Expense, ExpenseCategory, PayrollEntry,
                     StaffCompensation, Supplier)


class ExpenseForm(BaseForm):
    class Meta:
        model = Expense
        fields = ["category", "supplier", "group", "title", "amount", "method",
                  "paid_at", "document_number", "note"]
        widgets = {"paid_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
                   "note": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, kindergarten=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category"].queryset = ExpenseCategory.objects.filter(
            kindergarten=kindergarten, is_active=True)
        self.fields["supplier"].queryset = Supplier.objects.filter(
            kindergarten=kindergarten, is_active=True)
        self.fields["group"].queryset = Group.objects.filter(kindergarten=kindergarten)
        self.fields["amount"].validators.append(MinValueValidator(Decimal("0.01")))
        self.fields["amount"].widget.attrs.update({"min": "0.01", "step": "0.01"})


class ExpenseCategoryForm(BaseForm):
    class Meta:
        model = ExpenseCategory
        fields = ["name", "kind", "is_active"]

    def __init__(self, *args, kindergarten=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.kindergarten = kindergarten

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        if ExpenseCategory.objects.filter(
                kindergarten=self.kindergarten, name__iexact=name).exists():
            raise forms.ValidationError("Bu nomdagi xarajat kategoriyasi allaqachon mavjud.")
        return name


class SupplierForm(BaseForm):
    class Meta:
        model = Supplier
        fields = ["name", "inn", "phone", "bank_account", "note", "is_active"]

    def __init__(self, *args, kindergarten=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.kindergarten = kindergarten

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        if Supplier.objects.filter(
                kindergarten=self.kindergarten, name__iexact=name).exists():
            raise forms.ValidationError("Bu nomdagi yetkazib beruvchi allaqachon mavjud.")
        return name


class CompensationForm(BaseForm):
    class Meta:
        model = StaffCompensation
        fields = ["user", "monthly_salary", "effective_from", "note"]
        widgets = {"effective_from": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, kindergarten=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["user"].queryset = User.objects.filter(
            kindergarten=kindergarten, is_active=True)


class PayrollEntryForm(BaseForm):
    class Meta:
        model = PayrollEntry
        fields = ["advance", "bonus", "penalty", "status", "paid_at", "method", "note"]
        widgets = {"paid_at": forms.DateTimeInput(attrs={"type": "datetime-local"})}

    def clean(self):
        data = super().clean()
        base = self.instance.base_salary or Decimal("0")
        net = (base + (data.get("bonus") or 0) - (data.get("penalty") or 0)
               - (data.get("advance") or 0))
        if net < 0:
            raise forms.ValidationError(
                "Avans va jarima jami maosh hamda bonusdan oshmasligi kerak")
        if data.get("status") == PayrollEntry.Status.PAID:
            if not data.get("paid_at"):
                data["paid_at"] = timezone.now()
            if not data.get("method"):
                self.add_error("method", "To'langan ish haqi uchun usul majburiy")
        return data


class AnnouncementForm(BaseForm):
    def __init__(self, *args, kindergarten=None, **kwargs):
        super().__init__(*args, **kwargs)
        if kindergarten is not None:
            self.fields["group"].queryset = kindergarten.groups.filter(is_active=True)

    def clean(self):
        data = super().clean()
        if data.get("audience") == Announcement.Audience.GROUP and not data.get("group"):
            self.add_error("group", "Ma'lum guruh uchun guruhni tanlang")
        if data.get("audience") != Announcement.Audience.GROUP:
            data["group"] = None
        return data

    class Meta:
        model = Announcement
        fields = ["title", "text", "audience", "group", "send_at"]
        widgets = {"text": forms.Textarea(attrs={"rows": 4}),
                   "send_at": forms.DateTimeInput(attrs={"type": "datetime-local"})}
