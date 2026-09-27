from django import template
from apps.kitchen.units import display_quantity

register = template.Library()


@register.filter
def kitchen_quantity(grams, ingredient):
    if grams is None:
        return "—"
    value, unit = display_quantity(grams, ingredient.display_unit,
                                   ingredient.gram_per_piece)
    text = f"{value:,.2f}".rstrip("0").rstrip(".").replace(",", " ")
    return f"{text} {unit}"
