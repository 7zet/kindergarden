# Hissa qo'shish

## Lokal tayyorlash

1. Python 3.13, PostgreSQL 16 va Redis 7 o'rnating.
2. `.env.example`dan `.env` yarating va lokal qiymatlarni kiriting.
3. Virtual muhitda `pip install -r requirements.txt` ishlating.
4. `python manage.py migrate` va `python -m pytest -q` bajaring.

## O'zgarish qoidalari

- Barcha tenant querysetlari `kindergarten` bilan cheklanishi shart.
- Pul va miqdorda `Decimal` ishlatiladi.
- Moliyaviy/ombor tarixini hard-delete qilmang; storno yoki arxiv ishlating.
- Muhim yozuvlarda audit va atomar transaction bo'lishi kerak.
- Yangi biznes qoida avval test bilan yopiladi.
- Migration va hujjatlarni kod bilan bir PRda yuboring.

## Pull requestdan oldin

```powershell
python manage.py makemigrations --check --dry-run
python manage.py check
python -m pytest -q
```

