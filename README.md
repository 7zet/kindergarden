# Bog'cha OS — boshqaruv platformasi

Django 5 + PostgreSQL asosidagi ko'p tenantli bog'cha boshqaruv tizimi. Bolalar,
guruhlar, davomat, kirish-chiqish, billing, kassa, xodimlar, Telegram va
oziq-ovqat/ombor jarayonlarini birlashtiradi.

## Ishga tushirish

```
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
```

PostgreSQL bazasi va kuchli parolni yarating, `.env` ni to'ldiring, so'ng:

```powershell
python manage.py migrate
python manage.py seed
python manage.py runserver
```

Brauzer: http://127.0.0.1:8000

## Sifat holati

- Django system check: toza
- Avtomatik testlar: 102 ta
- CI: PostgreSQL 16 + Redis 7 + Python 3.13
- Ma'lumotlar bazasi: faqat PostgreSQL

GitHubga yuborilmaydi: `.env`, backup/dump, log, media, virtual muhit,
Celery schedule va yig'ilgan static fayllar.

## Yangi bog'cha ochish

Demo ma'lumotlarsiz bog'cha, standart moliyaviy siyosat, Direktor/Buxgalter/
Tarbiyachi rollari va egasi hisobini bitta buyruqda yarating:

```
python manage.py onboard_kindergarten --name "Yangi bog'cha" --owner-name "Egasi F.I.O." --owner-phone "+998901234567" --password "kuchli-parol"
```

Productionda `.env.example` asosida `DJANGO_DEBUG=False`, aniq domenlar, kuchli
`SECRET_KEY`, PostgreSQL va HTTPS sozlanishi shart. Batafsil: `DEPLOY.md`.

## Telegram bot va kirish/chiqish

`.env` ichida `TELEGRAM_BOT_TOKEN`, `TELEGRAM_BOT_USERNAME`, uzun tasodifiy
`TELEGRAM_WEBHOOK_SECRET`, `PUBLIC_BASE_URL` va `TELEGRAM_MINI_APP_URL` ni
kiriting. HTTPS domen ishga tushgach webhookni o'rnating:

```
python manage.py set_telegram_webhook
```

Telegram xabarlari, avtomatik invoyslar, qarz eslatmalari, e'lonlar va rahbarning
kun yakuni uchun Redis hamda ikkita fon jarayoni ishlashi kerak:

```powershell
celery -A config worker --pool=solo --loglevel=INFO
celery -A config beat --loglevel=INFO
```

Linux serverda worker uchun standart prefork pool ishlatiladi (`--pool=solo`
faqat Windows uchun). Redis uzilib qolsa xabarlar PostgreSQL outbox jadvalida
saqlanadi va ulanish tiklanganda qayta yuboriladi.

Xodim uchun `Qabul xodimi` rolini bering yoki rolga check-in/check-out
ruxsatlarini belgilang. Ota-onani bola kartasidagi kontakt yonidagi
`Telegram` tugmasi orqali 15 daqiqalik bir martalik havola bilan ulang.

| Kirish | Telefon | Parol |
|---|---|---|
| Egasi | +998901112233 | admin123 |
| Tarbiyachi | +998901112244 | admin123 |

`seed` demo ma'lumot yaratadi: 18 bola, 3 guruh, 3 tarif, 3 oylik invoys,
davomat va to'lovlar. Toza muhit uchun yangi PostgreSQL baza yarating va
`migrate` ni ishga tushiring.

## Bo'limlar

- **Boshqaruv** — oylik hisoblangan/yig'ilgan/qarz, eng eski qarzdorlar
- **Guruhlar** — guruh kartasi + kunlik davomat ekrani
- **Bolalar** — reestr, shartnoma, to'liq moliyaviy tarix
- **To'lovlar** — invoyslar (chiqarish tugmasi bilan) va tushgan to'lovlar
- **Qarzlar** — ochiq qoldiqlar, kechikish kunlari bilan
- **Hisobot** — oylar bo'yicha yig'ilish foizi, guruhlar kesimi
- **Sozlamalar** — moliyaviy siyosat, tariflar, chegirmalar, rollar
- **Oshxona** — kunlik taomnoma, taom normasi, masalliqlar, ombor kirim-chiqimi,
  muzlatilgan reja, haqiqiy sarf, storno va oylik Excel hisobot

## Asosiy qarorlar

**Qoldiq saqlanmaydi.** `Invoice.objects.with_balance()` orqali hisoblanadi.
Ikkita manba bo'lsa, ular albatta bir-biriga to'g'ri kelmay qoladi.

**Tarif versiyalanadi.** Tahrirlanmaydi — narx o'zgarsa yangi qator qo'shiladi.
Invoysga summa nusxalanadi, shuning uchun o'tgan oylar hisoboti o'zgarmaydi.

**Davomat billing summasini bevosita o'zgartirmaydi.** Faqat "butun oy
kelmadi" siyosati billingga ta'sir qiladi. Oshxona modulida tasdiqlash paytidagi
kelgan bolalar soni taomnoma rejasiga muzlatib nusxalanadi.

**Ombor qoldig'i saqlanmaydi.** `StockMove` ledgeridan kirim minus chiqim
sifatida hisoblanadi. Harakat o'chirilmaydi; xato operatsiya storno qilinadi.

**Bitta super rol.** `is_owner=True` bo'lgan foydalanuvchi yangi rol yaratadi
va unga ruxsat beradi. Kodda rol nomi tekshirilmaydi, faqat ruxsat.

**Taqsimot eng eski qarzdan.** Qattiq qoida, sozlama emas.
Ortiqcha summa avansda qoladi va keyingi invoysga avtomatik yopiladi.

**Idempotentlik.** Invoys generatsiyasini necha marta chaqirsangiz ham
dublikat chiqmaydi. To'lov `method + external_id` bo'yicha yagona —
Payme ikki marta webhook yuborsa, ikkinchisi yozilmaydi.

## Sozlanadigan siyosat

Sozlamalar bo'limida: oy o'rtasida kirish/chiqish (kunlar bo'yicha / yarim oy
/ to'liq oy), butun oy kelmasa (to'liq / foiz bilan / olinmaydi), invoys
chiqadigan kun, to'lov muddati, yaxlitlash qadami, ortiqcha to'lov rejimi.

## Tuzilma

```
apps/
  accounts/    User, Role, AuditLog
  school/      Kindergarten, BillingPolicy, WorkingCalendar,
               Tariff, Discount, Group, Child, Person, ContactChild, Enrollment
  attendance/  Attendance, MonthLock
  billing/     Invoice, InvoiceLine, Payment, Allocation
               engine.py    <- barcha hisob-kitob, Django'siz, 12 ta test
               services.py  <- bazaga tegadigan operatsiyalar
  web/         views, forms, urls
  kitchen/     taomnoma, retseptura, masalliq, ombor va reja/fakt
templates/
```

Kontakt identity modeli telefon raqamiga bog'liq emas. `Person` haqiqiy odamni,
`ContactChild` esa odamning muayyan bola bilan aloqasi va aynan shu bola uchun
`can_pickup`, `is_payer`, `has_app_access` kabi ruxsatlarni saqlaydi. Bir odam
bir nechta bolaga ulanadi va bitta aylanuvchi QR bilan o'ziga biriktirilgan
bolalarni ochadi. Bir xil telefonli yozuvlar avtomatik birlashtirilmaydi;
Sozlamalar → Kontakt shaxslar bo'limida administrator tasdig'i talab qilinadi.

`engine.py` Django'ni import qilmaydi. Summa noto'g'ri chiqsa — faqat shu
faylga qaraysiz. `python -m pytest` bilan tekshiring.

## Keyingi qadamlar

1. Pilot bog'chada oshxona normativlari va real ombor jarayonini sinash
2. Payme / Click webhook (merchant shartnomasi olingach)
3. Zaxiradan tiklash va 500 bola bilan yuklama sinovi

## Xavfsizlik va hissa qo'shish

- Xavfsizlik muammolari: [SECURITY.md](SECURITY.md)
- Development qoidalari: [CONTRIBUTING.md](CONTRIBUTING.md)
- Deployment: [DEPLOY.md](DEPLOY.md)
- Litsenziya: proprietary, barcha huquqlar himoyalangan
