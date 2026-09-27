"""Ruxsat tekshiruvi.

Ikki daraja:
1. Ruxsat kodi — nimaga kirish mumkin (Django Permission)
2. Qamrov — qaysi ma'lumotni ko'rish mumkin (masalan, faqat o'z guruhi)

Egasi (is_owner) barcha tekshiruvdan o'tadi.
"""

from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.utils import timezone

from apps.school.models import Group

# Ruxsat kodlari
VIEW_FINANCE = "billing.view_invoice"
EDIT_FINANCE = "billing.add_invoice"
TAKE_PAYMENT = "billing.add_payment"
VIEW_CHILD = "school.view_child"
EDIT_CHILD = "school.add_child"
EDIT_GROUP = "school.add_group"
MARK_ATTENDANCE = "attendance.add_attendance"
VIEW_ALL_GROUPS = "school.view_all_groups"
EDIT_SETTINGS = "school.change_billingpolicy"
MANAGE_USERS = "accounts.add_user"
VIEW_APPLICATION = "school.view_application"
EDIT_APPLICATION = "school.add_application"
CHECK_IN = "attendance.check_in_child"
CHECK_OUT = "attendance.check_out_child"
MANUAL_CHECK = "attendance.manual_check_child"
VIEW_KITCHEN = "kitchen.view_dailymenu"
EDIT_MENU = "kitchen.add_dailymenu"
EDIT_STOCK = "kitchen.add_stockmove"
APPROVE_MENU = "kitchen.change_dailymenu"


def require(*perms):
    """View'ga kirish uchun kamida bitta ruxsat kerak."""
    def decorator(view):
        @wraps(view)
        @login_required
        def wrapper(request, *args, **kwargs):
            if not any(request.user.has_perm(p) for p in perms):
                raise PermissionDenied("Bu bo'limga ruxsatingiz yo'q.")
            return view(request, *args, **kwargs)
        return wrapper
    return decorator


def visible_groups(user, kindergarten):
    """Tarbiyachi faqat o'ziga biriktirilgan guruhlarni ko'radi."""
    qs = Group.objects.filter(kindergarten=kindergarten)
    if user.has_perm(VIEW_ALL_GROUPS):
        return qs
    return qs.filter(teachers=user)


def check_group(user, group):
    """Guruhga kirish huquqini tekshiradi, yo'q bo'lsa 403."""
    if user.has_perm(VIEW_ALL_GROUPS):
        return
    if not group.teachers.filter(pk=user.pk).exists():
        raise PermissionDenied("Bu guruh sizga biriktirilmagan.")


def visible_children(user, kindergarten):
    """Tarbiyachi faqat o'z guruhidagi bolalarni ko'radi."""
    from apps.school.models import Child
    qs = Child.objects.filter(kindergarten=kindergarten, is_archived=False)
    if user.has_perm(VIEW_ALL_GROUPS):
        return qs
    today = timezone.localdate()
    return qs.filter(
        enrollments__group__teachers=user,
        enrollments__started_at__lte=today,
    ).filter(
        Q(enrollments__ended_at__isnull=True) |
        Q(enrollments__ended_at__gte=today)
    ).distinct()
