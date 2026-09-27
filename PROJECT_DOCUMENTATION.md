# Bog‘cha boshqaruv platformasi — to‘liq loyiha hujjati

> Hujjat holati: 2026-09-15. Ushbu hujjat `README.md` yoki eski `TODO.md` dagi
> rejalarga emas, joriy kodga asoslangan. Maxfiy `.env` qiymatlari ataylab
> keltirilmagan.

## 1. Loyiha nima?

Bu loyiha xususiy bog‘chaning kundalik operatsiyalari, bolalar reestri,
guruhlar, davomat, kirish-chiqish xavfsizligi, oylik hisob-kitoblar, qarzlar,
xarajatlar, ish haqi, kassa, hujjatlar va ota-onalar bilan Telegram orqali
aloqani bitta tizimda boshqaradigan web-platformadir.

Mahsulotni hozir quyidagicha taqdim etish to‘g‘ri:

**“Bog‘cha uchun bolalar, davomat, kirish-chiqish, moliya va Telegram
avtomatizatsiyasini birlashtirgan boshqaruv platformasi.”**

U klassik buxgalteriya dasturini to‘liq almashtirmaydi: soliq hisobi,
provodkalar, bank-ekvayring va fiskal chek integratsiyasi hozir mavjud emas.

## 2. Loyiha joylashuvi

Windows’dagi to‘liq yo‘l:

```text
C:\Users\ahror\Projects\bogcha-v3\kg
```

Foydalanuvchi aytgan `../bogcha-v3/kg/` shu loyiha papkasiga mos.

Asosiy kirish nuqtalari:

- `manage.py` — Django boshqaruv buyruqlari;
- `config/settings.py` — konfiguratsiya;
- `config/urls.py` — umumiy URL marshrutlari;
- `config/celery.py` — Celery ilovasi;
- `apps/` — biznes modullari;
- `templates/` — serverda render qilinadigan interfeys;
- `locale/` — tarjima kataloglari.

## 3. Texnologiyalar

| Qatlam | Texnologiya | Vazifasi |
|---|---|---|
| Backend | Python 3, Django 5.2 | Web, ORM, autentifikatsiya, formalar, admin |
| Ma’lumotlar bazasi | PostgreSQL + psycopg 3 | Yagona qo‘llab-quvvatlanadigan asosiy DB |
| Fon vazifalari | Celery 5 | Rejali va navbatdagi ishlar |
| Queue/cache transport | Redis; Windows’da Memurai | Celery broker va result backend |
| Frontend | Django Templates, HTML, CSS, vanilla JavaScript | Responsive boshqaruv paneli |
| Telegram | Telegram Bot API, webhook, Telegram Mini Apps | Ota-ona va xodim interfeyslari |
| QR | `qrcode` | Bola/kontakt QR tasvirlari |
| PDF | ReportLab | Invoys, kvitansiya, shartnoma, qarzdorlik hujjati |
| Excel | openpyxl | Boshqaruv hisobotini `.xlsx` eksport qilish |
| Static | WhiteNoise | Static fayllarni servis qilish |
| Config | python-decouple | `.env` qiymatlarini o‘qish |
| Test | pytest + pytest-django | Unit va integratsion testlar |
| Lokal HTTPS | ngrok | Telegram webhook/Mini App uchun vaqtinchalik HTTPS |
| Production | Gunicorn + Nginx + HTTPS | `DEPLOY.md` dagi tavsiya etilgan sxema |

`requirements.txt` dagi bevosita dependencylar:

```text
Django 5.2
python-decouple 3.8
whitenoise 6
psycopg[binary] 3
pytest 8
pytest-django 4
qrcode 8
reportlab 4
openpyxl 3
celery[redis] 5
```

## 4. Yuqori darajadagi arxitektura

```text
Brauzer / Telegram Mini App
             │
             ▼
        Django views
             │
     permissions + tenant scope
             │
      service / engine qatlami
        │             │
        ▼             ▼
   PostgreSQL      Celery queue
                         │
                         ▼
                  Redis / Memurai
                         │
                         ▼
                  Telegram Bot API
```

Muhim ajratishlar:

- `billing/engine.py` — Django va DB’dan mustaqil sof hisoblash yadrosi;
- `billing/services.py` — tranzaksion moliyaviy operatsiyalar;
- `attendance/services.py` — check-in/check-out qoidalari;
- `operations/services.py` — xarajat, kassa, ish haqi va outbox;
- `operations/tasks.py` — Celery vazifalari;
- `web/views.py` — HTTP/UI orkestratsiyasi;
- `web/telegram_views.py` — webhook va Mini App API’lari.

## 5. Django ilovalari

### `apps.accounts`

- telefon orqali kiradigan custom `User`;
- bog‘cha doirasidagi `Role`;
- Django permissionlaridan tuziladigan ruxsatlar;
- o‘chirilmaydigan `AuditLog`;
- joriy foydalanuvchini audit uchun context’da saqlaydigan middleware.

### `apps.school`

- bog‘cha va uning rekvizitlari;
- moliyaviy siyosat;
- ish kunlari kalendari;
- tarif va chegirmalar;
- guruh, bola va shartnomalar;
- qabul arizalari;
- `Person + ContactChild` professional kontakt modeli;
- Telegram akkauntlarini ulash;
- kontakt QR/kod passlari.

### `apps.attendance`

- kunlik davomat;
- oylik tabelni yopish/qayta ochish;
- check-in/check-out hodisalari;
- QR, ota-ona passi va qo‘lda usullar;
- olib ketish huquqi va direktor override’i;
- offline sinxronizatsiya metama’lumotlari.

### `apps.billing`

- invoys va invoys qatorlari;
- to‘lovlar;
- to‘lovni invoyslarga taqsimlash;
- proratsiya, chegirma va joy saqlash hisoblari;
- storno va qo‘lda tuzatishlar.

### `apps.operations`

- xarajat kategoriyalari;
- yetkazib beruvchilar;
- xarajatlar;
- kassa smenalari;
- xodim maoshi, bonus, avans va jarima;
- moliyaviy analytics;
- Excel/PDF boshqaruv hisobotlari;
- Telegram e’lonlari va ishonchli outbox;
- Celery avtomatizatsiyasi.

### `apps.web`

- sayt URL/view/formalari;
- role va scope tekshiruvlari;
- PDF hujjat generatorlari;
- Telegram webhook va Mini App endpointlari;
- uch tilli interfeys va eski shablonlar uchun tarjima ko‘prigi;
- xatolik sahifalari.

### `apps.kitchen`

- masalliqlar va minimal zaxira;
- yetkazib beruvchilar;
- taomlar va bir bolaga gramm normasi;
- kunlik taomnoma va davomatdan muzlatilgan reja;
- reja bo'yicha vaqtinchalik ombor chiqimi;
- fakt kiritilganda reja chiqimini storno qilib, fakt bo'yicha chiqim;
- o'chirilmaydigan `StockMove` ledgeri;
- oylik reja/fakt/qoldiq va Excel hisoboti.

## 6. Ma’lumotlar modeli

Ko‘p biznes jadvallarida UUID primary key ishlatiladi. Moliyaviy yoki tarixiy
yozuvlar odatda `PROTECT`, storno yoki arxiv orqali saqlanadi.

### 6.1 Kindergarten

Bog‘cha tenantini ifodalaydi:

- nomi va manzili;
- telefon;
- rasmiy/yuridik nom;
- STIR;
- bank nomi, hisob raqami va MFO;
- direktor F.I.O.;
- faol holati va yaratilgan vaqt.

Joriy arxitektura bitta bazada bir nechta bog‘chani ajrata oladi. UI’da har bir
foydalanuvchi faqat o‘z `kindergarten` yozuviga bog‘langan ma’lumotni ko‘radi.
Deployment strategiyasi esa har bir bog‘cha uchun alohida o‘rnatma sifatida ham
ishlatilishi mumkin.

### 6.2 BillingPolicy

Har bog‘chaga bitta moliyaviy siyosat:

- oy o‘rtasida kirish proratsiyasi: kunlik / yarim oy / to‘liq oy;
- oy o‘rtasida chiqish proratsiyasi;
- butun oy kelmagandagi rejim: to‘liq / foiz / olinmaydi;
- joy saqlash foizi;
- “butun oy kelmadi” chegarasi;
- invoys chiqarish kuni (1–28);
- to‘lov muddati kuni (1–28);
- ortiqcha to‘lovni avans sifatida saqlash;
- yaxlitlash qadami;
- valyuta (`UZS`).

### 6.3 WorkingCalendar

- bog‘cha + sana bo‘yicha yagona yozuv;
- ish kuni yoki dam olish kuni;
- izoh/bayram nomi;
- yozuv bo‘lmagan sanalarda dushanba–juma ish kuni deb olinadi;
- proratsiya va davomatga ta’sir qiladi.

### 6.4 Tariff va Discount

`Tariff`:

- nom;
- oylik summa;
- boshlanish va tugash sanasi;
- faol/nofaol holat.

Tarif tarixiy natijalarni buzmaslik uchun versiyalanadi: narx o‘zgarsa yangi
tarif ochiladi. Invoys yaratilganda summa invoys qatoriga nusxalanadi.

`Discount` foizli chegirmani va faol holatini saqlaydi.

### 6.5 Group

- nom;
- minimal/maksimal yosh;
- sig‘im;
- bitta tarbiyachiga maksimal bola nisbati;
- standart tarif;
- bir nechta tarbiyachi;
- asosiy tarbiyachi;
- ta’lim tili: o‘zbek/rus/ingliz/aralash;
- xona;
- ish boshlanish/tugash vaqti;
- faol holat.

Biznes nazoratlari:

- `age_from <= age_to` DB constraint va forma validatsiyasi;
- asosiy tarbiyachi avtomatik ravishda tarbiyachilar ro‘yxatiga qo‘shiladi;
- sig‘imda hozirgi va kelajakda boshlanadigan shartnomalar hisoblanadi;
- `open/full/over` bandlik holati;
- bola:tarbiyachi nisbati va limit oshishi hisoblanadi.

### 6.6 Child

- F.I.O.;
- tug‘ilgan sana va jins;
- avtomatik yoki qo‘lda ID kodi;
- manzil;
- allergiyalar;
- sog‘liq izohi;
- shifokor va telefon;
- umumiy izoh;
- arxiv holati;
- legacy child QR tokeni;
- yosh/yosh-oy ko‘rinishi;
- joriy shartnoma, asosiy kontakt, to‘lovchi va pickup kontaktlar.

### 6.7 Person va ContactChild

`Person` — haqiqiy odam: ona, ota, buvi, haydovchi va boshqalar.

- bog‘cha;
- F.I.O.;
- telefon va normalizatsiyalangan telefon;
- izoh;
- faol holat.

`Contact` (`ContactChild` proxy nomi bilan ham ishlaydi) — odam va aniq bola
orasidagi bog‘lanish:

- kimligi va kontakt turi;
- asosiy aloqa;
- to‘lovchi;
- bolani olib ketish huquqi;
- ota-ona kabinetiga kirish;
- moliyani ko‘rish;
- umumiy, davomat va moliyaviy xabarlarni olish;
- izoh.

Bir `Person` bir nechta bolaga ulanadi va har bola uchun ruxsatlari alohida
bo‘ladi. Telefon identity emas. Bir xil telefonli odamlar avtomatik merge
qilinmaydi; administrator Sozlamalar → Kontakt shaxslar orqali tasdiqlaydi.
Bir odam bir bolaga ikki marta ulanmaydi (`unique_person_child_contact`).

### 6.8 Enrollment

Bu bolaning guruh va tarif bilan shartnomasi:

- bola, guruh, tarif va ixtiyoriy chegirma;
- boshlanish/tugash sanasi;
- vaqtincha pauza va sabab;
- tugash sababi: bitirdi, ketdi, ko‘chdi, chiqarildi.

Status saqlanmaydi, sanalar va flaglardan hosil qilinadi:

- `enrolled` — qabul qilingan, hali boshlamagan;
- `active` — amaldagi;
- `paused` — vaqtincha to‘xtatilgan;
- `ended` — tugagan.

Guruh yoki tarif o‘zgarsa tarixni saqlash uchun eski shartnoma yopilib, yangisi
ochilishi kerak.

### 6.9 Application

Qabul voronkasi:

- bolaning ismi/tug‘ilgan sanasi;
- ota-ona va telefon;
- istalgan guruh/boshlash sanasi;
- manba va izoh;
- status: so‘rov, tanishuv, ariza, navbat, qabul, rad, yo‘qotilgan lead.

Qabul qilinganda `Child`, ota-ona `Person/Contact` va `Enrollment` bir
tranzaksiyada yaratiladi. Bir arizani qayta qabul qilish dublikat yaratmaydi.

### 6.10 Attendance va MonthLock

Bir shartnoma + bir sana uchun bitta davomat:

- keldi yoki kelmadi;
- sabab: kasal, oilaviy, ta’til, sababsiz;
- kelgan/ketgan vaqt;
- hujjat borligi;
- izoh;
- kim va qachon belgilagani.

Dam olish kunida davomat kiritish bloklanadi. Avval kalendarda sanani ish kuni
qilish kerak. `MonthLock` bilan guruh tabeli yopiladi; yopilgan oyni tarbiyachi
o‘zgartira olmaydi. Vakolatli foydalanuvchi sabab bilan qayta ochadi.

### 6.11 CheckEvent

O‘chirilmaydigan kirish/chiqish dalolatnomasi:

- bola shartnomasi;
- `in/out`;
- aniq vaqt;
- QR, qo‘lda yoki ota-ona pass usuli;
- topshirgan/olib ketgan kontakt;
- qayd qilgan xodim;
- idempotency key;
- direktor override’i va sabab;
- GPS koordinatalari (ruxsat bo‘lsa);
- qurilma ma’lumoti;
- offline sinxronlangan flag.

### 6.12 Invoice, InvoiceLine, Payment, Allocation

`Invoice`:

- bog‘cha va shartnoma;
- yagona raqam;
- hisob davri;
- chiqarilgan va to‘lov muddati sanasi;
- umumiy summa;
- issued/partial/paid/void statusi;
- bitta shartnoma va oyga bitta invoys.

`InvoiceLine`:

- oylik, proratsiya, joy saqlash, chegirma yoki qo‘lda tuzatish;
- sarlavha, muzlatilgan summa va JSON metadata.

`Payment`:

- bola;
- naqd, Payme, Click, Uzum yoki bank o‘tkazmasi;
- provider `external_id`;
- musbat summa;
- qabul vaqti;
- storno holati;
- izoh va yaratgan xodim.

`Allocation` bitta to‘lovning bir qismini invoysga bog‘laydi. Bitta to‘lov bir
necha oyni yopishi mumkin. Taqsimlanmagan qism avans hisoblanadi.

### 6.13 Operations modellari

- `ExpenseCategory` — oziq-ovqat, ijara, kommunal, xo‘jalik, ish haqi,
  ta’lim yoki boshqa;
- `Supplier` — nom, STIR, telefon, bank hisobi;
- `Expense` — kategoriya, supplier, guruh, nom, summa, usul, sana, hujjat,
  izoh, storno va yaratuvchi;
- `CashShift` — kassir, ochilish qoldig‘i, naqd kirim/chiqim, kutilgan va
  amaldagi qoldiq, farq, yopish izohi;
- `StaffCompensation` — xodim oylik stavkasi;
- `PayrollEntry` — davr, asosiy maosh, avans, bonus, jarima, sof summa,
  status va to‘lov usuli;
- `NotificationOutbox` — Telegram xabarlari uchun durable queue;
- `Announcement` — rejalashtirilgan e’lon.

### 6.14 Kitchen modellari

- `Ingredient` — tenantga tegishli masalliq, kategoriya, ko'rsatish birligi,
  donali mahsulot og'irligi va minimal zaxira. Joriy qoldiq ustunda saqlanmaydi;
- `Dish` va `DishIngredient` — taom hamda bir bolaga gramm normasi;
- `DailyMenu` va `MenuDish` — bog'cha bo'yicha bir kunlik taomnoma;
- `MenuLine` — tasdiqlashda muzlatilgan reja va oshpaz kiritgan fakt;
- `StockMove` — musbat miqdordagi kirim/chiqim, manba, narx, hujjat va storno;
- `Supplier` — oshxona yetkazib beruvchisi.

Ombor qoldig'i `kirim − chiqim` agregati. Chiqimlar atomar tranzaksiya va
`select_for_update()` bilan himoyalanadi. Yetarli qoldiq bo'lmasa butun amal
rollback qilinadi. `quantity_g > 0` PostgreSQL constraint bilan tekshiriladi.

## 7. Funksional bo‘limlar

### 7.1 Boshqaruv dashboardi

- tanlangan oy bo‘yicha hisoblangan summa;
- yig‘ilgan summa va yig‘ilish foizi;
- barcha davrlardagi qarz;
- bolalar soni;
- eng eski qarzdorlar;
- guruhlarga tezkor o‘tish.

### 7.2 Bolalar

- faol/arxiv/barcha reestri;
- ism yoki telefon bo‘yicha qidiruv;
- guruh/status bo‘yicha filtr;
- ism, yosh va balans bo‘yicha tartiblash;
- pagination;
- bola kartasi: sog‘liq, kontakt, shartnoma, davomat, kirish-chiqish,
  invoys va to‘lov tarixi;
- yangi bola/tahrirlash;
- shartnoma ochish;
- kontakt yaratish, tahrirlash va o‘chirish;
- Telegram ulash kodi;
- PDF qarzdorlik dalolatnomasi.

### 7.3 Guruhlar

- sig‘im, rezerv, bugungi davomat;
- asosiy/yordamchi tarbiyachilar;
- yosh oralig‘i, xona, til va ish vaqti;
- bandlik va tarbiyachi nisbati;
- guruh kartasi va o‘quvchilar;
- kunlik davomat;
- oylik tabel;
- oy yopish va qayta ochish.

### 7.4 Qabul arizalari

- qabulgacha CRM/voronka;
- status va guruh bo‘yicha filtr;
- ariza yaratish/tahrirlash;
- arizadan bola + ota-ona kontakti + shartnoma yaratish.

### 7.5 Invoys va to‘lovlar

- oy bo‘yicha ommaviy invoys chiqarish;
- takroriy bosishda dublikat yaratmaslik;
- yangi qo‘shilgan bolaga joriy oy proratsiyasi;
- invoys qatorlari va balans;
- qo‘lda musbat/manfiy tuzatish qatori;
- invoysni o‘chirmasdan bekor qilish;
- to‘lovni eng eski qarzga avtomatik taqsimlash;
- ortiqcha pulni avansda qoldirish;
- to‘lov storno;
- qarz aging: muddati kelmagan, 1–30, 31–60, 60+;
- pul inputlarida `1,000,000.50` formatini qabul qilish.

### 7.6 Hujjatlar

ReportLab bilan yaratiladi:

- rasmiy PDF invoys;
- to‘lov kvitansiyasi;
- shartnoma PDF;
- bola bo‘yicha qarzdorlik dalolatnomasi;
- bog‘cha rekvizitlari, hujjat raqami va imzo joylari.

### 7.7 Moliya va operatsiyalar

- reja, tushum, operatsion xarajat va sof natija;
- to‘lov usullari kesimi;
- guruh rentabelligi: reja, tushum, bevosita xarajat, marja;
- qarzdorlik dinamikasi;
- davomat/check-in/check-out statistikasi;
- xarajatlar reestri, kategoriya, supplier va storno;
- kassa smenasini ochish/yopish va tafovut;
- xodim maoshi, avans, bonus, jarima, sof to‘lov;
- Excel va PDF boshqaruv hisoboti.

Sof natija operatsion ko‘rsatkich bo‘lib, to‘liq soliq/buxgalteriya foydasi emas.

### 7.8 Sozlamalar

- bog‘cha rekvizitlari;
- moliyaviy siyosat;
- tarif va chegirmalar;
- ish kunlari/bayram kalendari;
- kontakt shaxslarni nazoratli birlashtirish;
- audit jurnali;
- foydalanuvchi va rollar;
- interfeys tili.

### 7.9 Uch tilli interfeys

Qo‘llab-quvvatlanadi:

- o‘zbek lotin (`uz`);
- o‘zbek kirill (`uz-cyrl`);
- rus (`ru`).

Til Sozlamalar sahifasida tanlanib, Django language cookie’da saqlanadi.
Yangi matnlar Django gettext orqali, eski statik HTML matnlari esa aniq oq
ro‘yxatli `LegacyUiTranslationMiddleware` orqali tarjima qilinadi. Oq ro‘yxat
sababi: bola, guruh va xodim kabi foydalanuvchi ma’lumotlarini tasodifan
transliteratsiya qilmaslik.

Muhim joriy cheklov: web-interfeys tarjimasi eng keng qamrovli qism;
PDF va Telegram/Mini App matnlarining barcha kombinatsiyalari hali to‘liq
gettext katalogiga ko‘chirilmagan.

## 8. Billing biznes mantiqi

### 8.1 Oylik hisoblash

Asosiy summa — shartnomadagi tarifning oylik summasi.

Oy ichidagi qamrov ish kunlari bilan hisoblanadi:

```text
qamrov = shartnoma amal qilgan ish kunlari / oydagi jami ish kunlari
```

Kunlik rejimda shu nisbat, yarim oy rejimida 0.5 yoki 1.0, to‘liq rejimda
1.0 olinadi. Natija `rounding_step` bo‘yicha `ROUND_HALF_UP` bilan yaxlitlanadi.

### 8.2 Davomatning moliyaga ta’siri

Oddiy kelmagan kun uchun ovqat puli ayrilmaydi. Davomat faqat “butun oy
kelmadi” siyosatini aniqlashda ishlatiladi:

- to‘liq summa;
- joy saqlash foizi;
- umuman olinmaydi.

### 8.3 Chegirma

Proratsiya/joy saqlashdan keyingi subtotalga foiz sifatida qo‘llanadi va
alohida manfiy invoice line bo‘lib saqlanadi.

### 8.4 Idempotent invoys

`Enrollment + period` unique. Generatsiya oldin mavjudligini tekshiradi.
Tugmani qayta bosish eski invoysni takrorlamaydi, ammo hali invoysi yo‘q yangi
bola uchun invoys yaratadi.

### 8.5 To‘lov taqsimoti

To‘lovlar ochiq invoyslarga eng eski davrdan boshlab yoyiladi. Ortiqcha summa
`Payment.unallocated` bo‘lib avansda qoladi. Keyingi invoys yaratilganda avans
unga avtomatik yoyiladi.

### 8.6 Storno

- invoice void qilinsa allocationlar bo‘shatiladi va pul boshqa qarzlarga
  qayta yoyiladi;
- payment reverse qilinsa allocationlar o‘chadi va invoice statuslari qayta
  hisoblanadi;
- tarixiy yozuvning o‘zi o‘chirilmaydi.

## 9. Kirish-chiqish va QR xavfsizligi

### 9.1 Kontaktga tegishli QR

QR oilaga yoki bolaga emas, `Person`ga tegishli. Bir ona ikki bolaga ulangan
bo‘lsa, bitta skan shu onaga bog‘langan barcha ruxsat etilgan bolalarni chiqaradi.
Har bola uchun `can_pickup` alohida tekshiriladi.

### 9.2 Token tarkibi va tekshiruv

- token serverda imzolanadi;
- imzoda kontakt/person identifikatori va vaqt bor;
- maxfiy kalit telefonga berilmaydi;
- tekshiruv serverda bajariladi;
- QR qisqa muddatli, raqamli kod esa zaxira usul;
- kod bog‘cha doirasida resolve qilinadi;
- QR uchun cheklangan offline grace mavjud.

### 9.3 Check-in

- vakolatli xodim kontaktni skanerlaydi;
- unga ko‘rinadigan guruhlardagi bolalar chiqadi;
- allergiya/sog‘liq ogohlantirishi ko‘rsatiladi;
- tanlangan bolalar qabul qilinadi;
- vaqt, kontakt, xodim, usul, qurilma/GPS qayd etiladi;
- bir amal idempotency key bilan takrorlanishdan himoyalanadi.

### 9.4 Check-out

- kontaktning aynan shu bola uchun `can_pickup` huquqi tekshiriladi;
- ruxsatsiz bo‘lsa oddiy tasdiqlash mumkin emas;
- `override_check_child` vakolatli foydalanuvchi sabab yozib override qiladi;
- override audit/dalolatnoma ma’lumotida qoladi.

### 9.5 Zaxira yo‘llari

- 6 xonali kod;
- qo‘lda bola/kontakt tanlash — alohida permission bilan;
- Mini App’da offline queue va keyin sinxronlash;
- `synced_offline` orqali hisobotda ajratish;
- bir nechta tarbiyachi o‘z Telegram akkaunti bilan ishlashi mumkin.

## 10. Telegram bot va Mini Apps

### 10.1 Ota-ona ulanishi

Administrator bola kartasidagi kontakt uchun 15 daqiqalik, bir martalik
`TelegramLinkCode` yaratadi. Kontakt bot havolasini ochganda Telegram akkaunti
`Person` bilan bog‘lanadi. Bitta Telegram akkaunt bir nechta person yozuviga
bog‘lanishi mumkin, lekin oddiy biznes oqimida haqiqiy odamga bog‘lanadi.

### 10.2 Ota-ona Mini App

- Telegram `initData` imzosi serverda tekshiriladi;
- ota-ona shaxsi va bolalari serverdan olinadi;
- bola, guruh, davomat va ruxsat etilsa balans ko‘rsatiladi;
- kontaktning aylanuvchi QR kodi va zaxira kodi beriladi;
- ota-ona DB permissioniga qarab moliyani ko‘radi.

### 10.3 Xodim Mini App

- xodim uchun alohida bir martalik ulash kodi;
- `StaffTelegramAccount` orqali Telegram identity;
- xodim faqat o‘z permissioni va guruh scope’idagi bolalarni ko‘radi;
- QR/kodni resolve qilish;
- bir yoki bir nechta bolani check-in/out qilish;
- allergiya va pickup ruxsatini ko‘rsatish;
- manual/override huquqlari;
- ketma-ket skan oqimi;
- offline yuborilmagan amallar navbati.

### 10.4 Webhook

Endpoint:

```text
POST /telegram/webhook/
```

Webhook secret header bilan himoyalanadi. `set_telegram_webhook` buyrug‘i
Telegram’da joriy `PUBLIC_BASE_URL` asosidagi URL’ni o‘rnatadi.

### 10.5 Telegram xabarlari

Tizim navbatga qo‘ya oladi:

- invoys yaratildi;
- to‘lov qabul qilindi;
- bola kirdi/chiqdi;
- qarz yoki yaqin muddat eslatmasi;
- ertangi maxsus dam olish kuni;
- bog‘cha e’loni;
- rahbar uchun kun yakuni.

Kontaktning `receives_messages`, `notify_attendance`, `notify_billing` va
`can_see_billing` ruxsatlari hisobga olinadi.

## 11. Celery va ishonchli xabar navbati

Beat jadvali:

| Vazifa | Davri |
|---|---|
| Outbox yetkazish | har 60 soniya |
| Rejalashtirilgan e’lonlar | har 60 soniya |
| Avtomatik invoys | har kuni 06:00 |
| Kunlik biznes avtomatizatsiyasi | har kuni 18:05 |

`NotificationOutbox` PostgreSQL’da saqlanadi. Telegram vaqtincha ishlamasa:

- xabar yo‘qolmaydi;
- status `failed` bo‘ladi;
- urinishlar soni oshadi;
- exponential backoff bilan keyinga suriladi;
- maksimum 8 urinish;
- muvaffaqiyatli bo‘lsa `sent_at` yoziladi;
- `dedupe_key` takroriy xabarni bloklaydi.

## 12. Rollar va permissionlar

Kod rol nomiga tayanmaydi. `Role.permissions` orqali imkoniyat beriladi.
`is_owner` yoki superuser barcha ruxsatga ega.

Asosiy permission konstantalari:

- moliyani ko‘rish/tahrirlash;
- to‘lov qabul qilish;
- bola va guruhni ko‘rish/tahrirlash;
- davomat belgilash;
- barcha guruhlarni ko‘rish;
- sozlamalarni boshqarish;
- foydalanuvchilarni boshqarish;
- ariza ko‘rish/tahrirlash;
- check-in;
- check-out;
- qo‘lda check;
- ruxsatsiz pickup override.

Scope qoidasi:

- direktor/tegishli permission — barcha guruhlar;
- tarbiyachi — faqat `Group.teachers` orqali biriktirilgan guruhlar;
- bolalar ham shu guruh scope’i orqali filtrlanadi;
- har view bog‘chani foydalanuvchidan oladi va boshqa tenant ID’si bilan
  kelgan obyektga 404/403 beradi;
- sidebar permissionga qarab bo‘limlarni yashiradi.

Onboarding komandasi standart Direktor, Buxgalter, Tarbiyachi va Qabul xodimi
kabi permission to‘plamlarini yaratadi.

## 13. Audit va tarix daxlsizligi

Audit quyidagilar uchun yoziladi:

- invoice yaratish/void/qo‘lda qator;
- payment yaratish/reverse;
- kontakt va person merge;
- enrollment qabul/yopish/pauza;
- davomat va oy lock/unlock;
- xarajat/kassa operatsiyalari;
- muhim konfiguratsiya o‘zgarishlari.

`AuditLog.delete()` va `CheckEvent.delete()` ataylab bloklangan. Auditda:

- foydalanuvchi;
- action kodi;
- obyekt turi va ID;
- oldingi/keyingi JSON;
- izoh;
- vaqt saqlanadi.

## 14. Xavfsizlik

### Mavjud himoyalar

- PostgreSQL yagona DB; SQLite fallback yo‘q;
- `.env` orqali secret/config;
- tenant bo‘yicha queryset scope;
- view darajasida permission decorator;
- CSRF himoyasi;
- Django password hashing va validatorlar;
- HTTPS webhook;
- Telegram `initData` va webhook secret tekshiruvi;
- serverda QR imzosi;
- musbat payment/expense DB constraints;
- duplicate provider transaction constraint;
- invoice idempotentligi;
- atomic transactionlar;
- storno/audit, hard delete o‘rniga tarixni saqlash;
- productionda wildcard hostni taqiqlash;
- HSTS, SSL redirect, secure cookie, HttpOnly, SameSite;
- `X-Content-Type-Options`, referrer policy, clickjacking himoyasi;
- rotating app log.

### Production uchun operator javobgarligi

- kuchli va noyob `SECRET_KEY`;
- kuchli PostgreSQL paroli;
- `.env`ni repoga kiritmaslik;
- aniq `ALLOWED_HOSTS`;
- real domen va TLS;
- server firewall va OS update;
- DB backupni boshqa serverga nusxalash;
- backup restore’ni sinash;
- demo hisoblarini o‘chirish;
- xodim permissionlarini minimal berish;
- log/monitoring va incident jarayoni.

“Hech qachon hacker kira olmaydi” degan mutlaq kafolat texnik jihatdan mumkin
emas; loyiha qatlamli himoya beradi, lekin deployment va operatsion xavfsizlik
ham shart.

## 15. `.env` konfiguratsiyasi

Joriy kod ishlatadigan kalitlar:

```env
SECRET_KEY=
DJANGO_DEBUG=
ALLOWED_HOSTS=
CSRF_TRUSTED_ORIGINS=

DB_NAME=
DB_USER=
DB_PASSWORD=
DB_HOST=127.0.0.1
DB_PORT=5432
DB_SSLMODE=prefer

TIME_ZONE=Asia/Tashkent
PAGE_SIZE=50

TELEGRAM_BOT_TOKEN=
TELEGRAM_BOT_USERNAME=
TELEGRAM_WEBHOOK_SECRET=
PUBLIC_BASE_URL=
TELEGRAM_MINI_APP_URL=
TELEGRAM_STAFF_APP_URL=

# Ixtiyoriy; yozilmasa localhost Redis defaultlari ishlaydi
CELERY_BROKER_URL=redis://127.0.0.1:6379/0
CELERY_RESULT_BACKEND=redis://127.0.0.1:6379/1

SECURE_SSL_REDIRECT=
COOKIE_SECURE=
```

Secret qiymatlarni hujjat, screenshot, Git yoki chatga joylamaslik kerak.

## 16. Lokal ishga tushirish — Windows

### Birinchi tayyorlash

```powershell
cd C:\Users\ahror\Projects\bogcha-v3\kg
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python manage.py migrate
```

Demo kerak bo‘lsa bir marta:

```powershell
python manage.py seed
```

Toza bog‘cha:

```powershell
python manage.py onboard_kindergarten --name "Yangi bog'cha" --owner-name "Egasi F.I.O." --owner-phone "+998901234567" --password "kuchli-parol"
```

### Doimiy processlar

Terminal 1 — Django:

```powershell
.\.venv\Scripts\Activate.ps1
python manage.py runserver 127.0.0.1:8000 --noreload
```

Terminal 2 — Celery worker:

```powershell
.\.venv\Scripts\Activate.ps1
celery -A config worker --pool=solo --loglevel=INFO --hostname=bogcha-worker@%h
```

Terminal 3 — Celery beat:

```powershell
.\.venv\Scripts\Activate.ps1
celery -A config beat --loglevel=INFO --pidfile=
```

Terminal 4 — ngrok:

```powershell
ngrok http 8000
```

Ngrok URL o‘zgarsa `.env` dagi host/origin/public/Mini App URL’larini
yangilab, Django va Celery processlarini qayta ochish, so‘ng:

```powershell
python manage.py set_telegram_webhook
```

PostgreSQL va Memurai servis holati:

```powershell
Get-Service *postgres*
Get-Service Memurai
```

## 17. Production deployment

`DEPLOY.md` Ubuntu 22.04+ uchun quyidagi arxitekturani beradi:

- PostgreSQL;
- Python virtual environment;
- Gunicorn — 3 worker, localhost port;
- Nginx reverse proxy va static alias;
- Certbot TLS;
- systemd auto-restart;
- `pg_dump | gzip` kunlik backup;
- `check --deploy` va pytest release gate.

Productionda Celery worker, Celery beat va Redis uchun ham alohida systemd
unitlar qo‘shilishi kerak. Mavjud `DEPLOY.md`ning Gunicorn/Nginx qismi bor,
ammo Celery/Redis unitlari hali hujjatda to‘liq yozilmagan.

## 18. URL/API xaritasi

### Web

- `/` — dashboard;
- `/login/`, `/logout/`;
- `/children/`, child detail/edit/contact/enrollment/QR;
- `/groups/`, detail/edit/attendance/tabel/lock;
- `/applications/`, edit/accept;
- `/payments/`, received payments, debts;
- `/invoice/<id>/`, PDF, void, manual line;
- `/reports/`;
- `/settings/`, tariffs, discounts, calendar, audit, persons, users, roles;
- `/checkdesk/` — zaxira qo‘lda kirish-chiqish.

### Operations (`/finance/`)

- dashboard;
- expenses/categories/suppliers;
- cash shifts;
- payroll/compensation;
- announcements;
- management Excel/PDF.

### Telegram

- `/telegram/webhook/`;
- `/telegram/mini/`, `/telegram/mini/session/`;
- `/telegram/contact-qr/`, `/telegram/parent/credential/`;
- `/telegram/staff/`, bootstrap/resolve/confirm;
- legacy `/telegram/pickup/<token>/`.

### I18n

- `/i18n/setlang/` — til cookie’sini saqlash.

## 19. Management commandlar

```powershell
python manage.py migrate
python manage.py seed
python manage.py onboard_kindergarten ...
python manage.py run_billing --period YYYY-MM
python manage.py set_telegram_webhook
python manage.py check
python manage.py check --deploy
python -m pytest
```

`run_billing` davr berilmasa joriy oy uchun ishlaydi; servisning o‘zi
idempotent.

## 20. Testlar va sifat nazorati

Joriy kolleksiya: **102 ta test** (shu jumladan oshxona modulining 13 ta
biznes, xavfsizlik va integratsion testi).

Qamrov yo‘nalishlari:

- sof billing engine: proratsiya, chegirma, absence, rounding, allocation;
- invoice/payment service va audit;
- manfiy to‘lovni rad etish;
- yosh oralig‘i validatsiyasi;
- dam olish kunidagi davomatni bloklash;
- role/scope va tenant isolation;
- check-in/out va pickup permission;
- QR token/kod va sibling contacts;
- Telegram webhook/Mini App imzosi;
- staff Mini App;
- PDF hujjatlar;
- oshxona reja/fakt, ombor qoldig'i, storno va tenant permissionlari;
- operations, payroll, kassa, outbox va eksport;
- grouped money input;
- uch tilli UI;
- asosiy sahifalar smoke testlari.

Ishga tushirish:

```powershell
python -m pytest -q
python manage.py check
```

## 21. Muhim biznes afzalliklari

- bola, guruh, davomat va pul bitta tizimda;
- check-out’da kim olib ketgani va ruxsati aniq;
- allergiya ogohlantirishi operativ ekranda;
- kontaktga alohida QR va bir kontaktga bir nechta bola;
- tarixni o‘chirib yubormaydigan storno/audit;
- to‘lovni eng eski qarzga avtomatik yoyish;
- yangi bolaga joriy oy proratsiyasi;
- direktor uchun real tushum/xarajat/foyda ko‘rinishi;
- kassa smenasi va maosh moduli;
- PDF/Excel hujjatlar;
- Telegram orqali ota-ona va xodim oqimi;
- xabarlar internet uzilganda outbox’da qolishi;
- role-based va group-scoped access;
- PostgreSQL va production security sozlamalari;
- o‘zbek lotin, kirill va rus interfeysi.

## 22. Joriy cheklovlar va hal qilinmagan ishlar

Quyidagilarni sotuvdan oldin aniq tushuntirish kerak:

1. Payme/Click/Uzum usullari modelda bor, lekin real merchant webhook va
   avtomatik bank reconciliation endpointlari yo‘q.
2. Fiskal chek va soliq tizimi integratsiyasi yo‘q; PDF kvitansiya ichki hujjat.
3. SMS orqali standalone ota-ona kabineti yo‘q; Telegram Mini App mavjud.
4. Hujjat fayllarini upload/saqlash moduli yo‘q.
5. Oila/aka-uka chegirmasi avtomatik hisoblanmaydi.
6. Guruhdan guruhga ko‘chirish maxsus bitta tugmali workflow sifatida yo‘q;
   shartnomani yopib yangisini ochish bilan bajariladi.
7. Erta ketish uchun alohida davomat forma maydoni cheklangan; check-out vaqti
   `CheckEvent/Attendance.left_at` orqali qayd qilinadi.
8. PDF va Telegram/Mini App tarjimasining barcha matnlari uch tilda to‘liq
   yakunlanmagan.
9. 500+ bola bilan alohida load/performance testi hujjatlashtirilmagan.
10. Parallel payment race va restore drill bo‘yicha qo‘shimcha sinov kerak.
11. Production Celery/Redis systemd va observability runbook’i to‘liq emas.
12. Ngrok faqat lokal/pilot uchun; productionda doimiy domen va TLS kerak.
13. Mobil offline queue brauzer storage’iga tayanadi; keng real-device test
    zarur.
14. Mahsulot to‘liq 1C/buxgalteriya yoki davlat ERP’si emas.

Eski `TODO.md` dagi ayrim “yo‘q” bandlar hozir amalda bajarilgan: Telegram,
PDF invoys/kvitansiya, e’lonlar, Celery eslatmalar, Excel/PDF management report,
xarajat, kassa, payroll va ota-ona Mini App shular jumlasidan.

## 23. Tavsiya etiladigan sotuv/onboarding jarayoni

1. Bog‘cha bilan rekvizit, tarif, proratsiya va to‘lov siyosatini kelishish.
2. Toza PostgreSQL baza va alohida deployment yaratish.
3. `onboard_kindergarten` bilan owner va standart rollarni ochish.
4. Xodimlar va minimal permissionlarni kiritish.
5. Guruh, tarif, kalendar va bolalarni import/kiritish.
6. Kontakt/pickup huquqlarini ota-onalar bilan tasdiqlash.
7. Telegram akkauntlarini bir martalik kod bilan ulash.
8. Bir guruhda 2–4 hafta parallel pilot.
9. Buxgalter raqamlari bilan invoice/payment/xarajatni solishtirish.
10. Backup restore va incident ssenariysini sinash.
11. Keyin barcha guruhlarga yoyish.

## 24. Kod bilan ishlash qoidalari

- pul qoidasi o‘zgarsa avval `billing/engine.py` testi;
- balansni alohida ustun qilib saqlamaslik;
- moliyaviy yozuvni hard delete qilmaslik;
- har querysetda tenant scope;
- har yangi view’da permission;
- Telegram ishini HTTP request ichida ishonchsiz “fire and forget” qilmaslik,
  outbox ishlatish;
- schema o‘zgarishida migration va backup;
- yangi UI matnini gettext katalogiga qo‘shish;
- release oldidan `pytest`, `check --deploy`, backup restore;
- demo ma’lumotni productionga olib chiqmaslik.

## 25. Qisqa yakun

Loyiha oddiy “bolalar ro‘yxati”dan ancha katta: u qabul voronkasi, shartnoma,
davomat, xavfsiz pickup, invoice/payment allocation, qarz, xarajat, kassa,
payroll, audit, PDF/Excel, Telegram Mini Apps va fon avtomatizatsiyasini bir
arxitekturaga birlashtiradi. Eng kuchli texnik tomonlari — sof billing engine,
PostgreSQL tranzaksiyalari, idempotent operatsiyalar, `Person/ContactChild`
modeli, role/scope himoyasi va durable Telegram outbox. Sotuvga chiqishdan oldin
asosiy qolgan ishlar — real payment provider/fiskal integratsiya, barcha tashqi
hujjat/xabarlarning to‘liq lokalizatsiyasi, load testi va production operational
runbook’ni yakunlash.
