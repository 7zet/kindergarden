import re


def normalize_phone(value):
    digits = re.sub(r"\D", "", value or "")
    if len(digits) == 9:
        digits = "998" + digits
    return digits
