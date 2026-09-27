from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.school.models import Kindergarten

from .models import ExpenseCategory


@receiver(post_save, sender=Kindergarten)
def create_default_expense_categories(sender, instance, created, **kwargs):
    if not created:
        return
    defaults = [
        ("Oziq-ovqat", "food"), ("Ijara", "rent"),
        ("Kommunal to'lovlar", "utilities"), ("Xo'jalik xarajatlari", "household"),
        ("Ta'lim materiallari", "education"), ("Boshqa xarajatlar", "other"),
    ]
    ExpenseCategory.objects.bulk_create([
        ExpenseCategory(kindergarten=instance, name=name, kind=kind)
        for name, kind in defaults
    ], ignore_conflicts=True)
