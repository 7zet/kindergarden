from decimal import Decimal

from django import template
from django.utils.translation import get_language

from apps.web.ui_translation import ui_text

register = template.Library()


@register.filter
def som(value):
    """1400000 -> 1 400 000"""
    if value is None or value == "":
        return "—"
    try:
        v = Decimal(value)
    except Exception:
        return value
    sign = "-" if v < 0 else ""
    return sign + f"{abs(v):,.0f}".replace(",", " ")


@register.filter
def pct(value, total):
    try:
        if not total:
            return 0
        return round(Decimal(value) / Decimal(total) * 100)
    except Exception:
        return 0


@register.simple_tag
def tr(text):
    """Translate UI fragments, including fragments next to dynamic values."""
    return ui_text(text)


@register.filter
def compact_som(value):
    """Human-readable chart scale number; the chart renders the unit once."""
    try:
        number = Decimal(value)
    except Exception:
        return value
    absolute = abs(number)
    if absolute >= Decimal("1000000"):
        shown = number / Decimal("1000000")
        return f"{shown:.1f}".rstrip("0").rstrip(".")
    if absolute >= Decimal("1000"):
        shown = number / Decimal("1000")
        return f"{shown:.0f}K"
    return f"{number:.0f}"


@register.filter
def phone_display(value):
    digits = "".join(char for char in str(value or "") if char.isdigit())
    if len(digits) == 12 and digits.startswith("998"):
        return f"+998 {digits[3:5]} {digits[5:8]} {digits[8:10]} {digits[10:12]}"
    return value or "—"
