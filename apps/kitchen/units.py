from decimal import Decimal, InvalidOperation


def to_grams(value, unit="kg", gram_per_piece=None):
    try:
        amount = Decimal(str(value).replace(",", ".").replace(" ", ""))
    except (InvalidOperation, TypeError):
        raise ValueError("Miqdor noto'g'ri kiritildi")
    if amount <= 0:
        raise ValueError("Miqdor musbat bo'lishi kerak")
    if unit in {"kg", "litr"}:
        return (amount * Decimal("1000")).quantize(Decimal("0.01"))
    if unit == "dona":
        if not gram_per_piece:
            raise ValueError("Donali mahsulot uchun bir dona og'irligi kiritilmagan")
        return (amount * Decimal(gram_per_piece)).quantize(Decimal("0.01"))
    if unit == "g":
        return amount.quantize(Decimal("0.01"))
    raise ValueError("Noma'lum o'lchov birligi")


def display_quantity(grams, unit="kg", gram_per_piece=None):
    grams = Decimal(grams or 0)
    if unit == "dona" and gram_per_piece:
        return grams / Decimal(gram_per_piece), "dona"
    return grams / Decimal("1000"), "litr" if unit == "litr" else "kg"

