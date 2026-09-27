# Bog'cha OS — amaldagi vazifalar

> Holat: 2026-09-15. Bajarilgan bandlar joriy kod va 102 ta avtomatik testga
> asoslangan. Production tashqi infratuzilma ishlari alohida belgilanadi.

## Tayyor asosiy modullar

- [x] PostgreSQL yagona ma'lumotlar bazasi va tenant scope
- [x] Role/permission tizimi va tarbiyachining guruh scope'i
- [x] Bolalar, kontakt shaxslar, hujjatlar va shartnomalar
- [x] Shartnoma overlap, sig'im va yosh validatsiyasi hamda guruhga ko'chirish
- [x] Davomat, oylik tabel, oy yopish/qayta ochish
- [x] QR check-in/check-out, pickup permission va audit
- [x] Invoys, proratsiya, chegirma, payment allocation va storno
- [x] PDF invoys, kvitansiya, shartnoma va qarzdorlik dalolatnomasi
- [x] Xarajat, kassa smenasi, ish haqi va boshqaruv hisobotlari
- [x] Telegram bot, Mini App, e'lon, outbox va Celery avtomatizatsiyasi
- [x] Uch til, global qidiruv, print va responsive UI
- [x] Health endpoint, Celery heartbeat va Sentry sozlamasi

## Oshxona — 1-bosqich

- [x] Masalliqlar katalogi va minimal zaxira
- [x] Qoldiqni `StockMove` ledgeridan hisoblash (`current_stock` ustuni yo'q)
- [x] Taom va bir bolaga gramm normasi
- [x] Davomatdan muzlatiladigan kunlik reja
- [x] Reja bo'yicha vaqtinchalik ombor chiqimi
- [x] Fakt kiritilganda reja chiqimini storno qilish va fakt chiqimi
- [x] Manfiy qoldiqni transactional lock bilan bloklash
- [x] Musbat miqdor uchun PostgreSQL constraint
- [x] Oylik reja/fakt/qoldiq hisoboti va Excel eksport
- [x] Tenant, permission, idempotentlik va storno testlari
- [ ] Pilot bog'chada real normativ va ombor qoldig'i bilan solishtirish

## Productiondan oldin

- [ ] Yangi PostgreSQL bazaga backup restore drill o'tkazish
- [ ] 500 bola, 12 oy invoys va katta ombor ledgerida yuklama testi
- [ ] Real rollarga oshxona permissionlarini taqsimlash
- [ ] Oshpaz telefoni va sekin internetda mobil sinov
- [ ] Production domen, HTTPS, webhook va monitoring
- [ ] Demo akkauntlar/test ma'lumotlarini productiondan ajratish
- [ ] Bayram kalendari, tariflar va oshxona boshlang'ich qoldiqlarini kiritish

## Keyingi biznes ishlari

- [ ] Excel orqali bolalar importi: preview, validatsiya va audit
- [ ] Household/oila chegirmasi qoidalarini real mijoz bilan aniqlash
- [ ] Bandlik prognozi va churn drill-down
- [ ] Ochiq qabul arizasi uchun spam/rate-limit himoyasi
- [ ] Payme/Click — merchant shartnomasi va sandbox credentialdan keyin
- [ ] Oshxona 2-bosqich: mavsumiy menyu, buyurtma, yaroqlilik muddati,
  brak jurnali va moliyaga tasdiqlangan xarajat uzatish

## Doimiy sifat qoidalari

1. Pul va miqdorda `Decimal`; `float` biznes hisobida ishlatilmaydi.
2. Moliyaviy va ombor yozuvi o'chirilmaydi — storno/audit ishlatiladi.
3. Har queryset tenant bo'yicha cheklanadi.
4. Muhim operatsiya transaction va kerak joyda `select_for_update()` bilan.
5. Har o'zgarishdan keyin `manage.py check` va to'liq `pytest` ishlatiladi.
