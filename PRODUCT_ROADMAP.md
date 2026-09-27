# Bog‘cha platformasi — ustuvor tuzatish va mahsulot roadmap’i

> Yangilangan sana: 2026-09-15. Manba: joriy kod, `PROJECT_DOCUMENTATION.md`,
> AI bergan biznes xulosalari va loyihadagi oldingi qarorlar.

## Amalga oshirish holati (2026-09-15)

- ✅ Attendance/CheckEvent invariantlari, manual event oqimi va consistency audit/fix.
- ✅ Multi-tenant invoice raqami hamda provider transaction scope.
- ✅ `Person` + `ContactChild` professional kontakt modeli.
- ✅ Excel/PDF hisobot, kassa, xarajat, ish haqi, rentabellik va Telegram outbox.
- ✅ Guruhdan guruhga atomar ko'chirish workflow'i.
- ✅ Private bola hujjati: PDF/JPEG/PNG signature, 10 MB limit, tenantli download,
  audit va soft archive.
- ✅ Oshxona 1-bosqichi: taomnoma, norma, masalliq, ombor ledger, reja/fakt,
  storno va Excel hisoboti.
- ⏳ Excel onboarding importi, family policy, occupancy/churnning to'liq UI va
  public application formasi keyingi implementatsiya blokida.
- ⛔ Payme/Click real pul oqimi merchant shartnomasi va test credentialgacha
  ataylab bloklangan; bu avvalgi biznes qarorini saqlaydi.

## Production yetuklik qo'shimcha roadmap'i

### A — Ishonchlilik

- ✅ PostgreSQL backup olindi va migratsiyadan oldin tekshirildi.
- ✅ `/health/`: PostgreSQL, Redis va 3 daqiqalik Celery heartbeat.
- ✅ Celery worker/beat uchun systemd unitlari `DEPLOY.md`ga qo'shildi.
- ✅ Sentry xavfsiz konfiguratsiyasi (`send_default_pii=False`).
- ✅ Outbox monitoring va qo'lda retry ekrani.
- ⏳ Alohida bo'sh bazaga restore drill production nusxasi bilan bajariladi.
- ⏳ Tashqi uptime monitor domen chiqqach `/health/`ga ulanadi.

### B — Biznes chekka holatlari

- Moliyaviy davr locki va retroaktiv davomat ta'siri preview/recalculation;
- avans refund/storno workflow'i;
- qaytgan bola va eski qarz testi;
- oy o'rtasidagi transferni ikki tarifga proratsiya qilish testi;
- egizaklar, leap-year, due-day, yil almashinuvi va policy-version testlari.

### C — Mustaqil foydalanish

- Excel preview/import, onboarding wizard, human-readable error katalogi;
- BillingPolicy yordam matnlari, bulk preview/action va print stylesheet;
- video qo'llanma kontenti real UI barqarorlashgach yoziladi.

### D — Operatsion yetuklik

- to'liq tenant export, changelog/version ekrani, support SLA;
- 500 bola/12 oy/5000 to'lov load testi va real device matrix.

## Asosiy qarorlar

1. **Asosiy SaaS arxitektura — bitta multi-tenant o‘rnatma.** Har bog‘cha
   `Kindergarten` orqali ajratiladi. Alohida deployment faqat yirik mijoz,
   qonuniy/data-residency talabi yoki enterprise shartnoma bo‘lsa taklif qilinadi.
2. **CheckEvent — kirish/chiqishning birlamchi dalili.** Attendance — undan va
   qo‘lda kiritilgan absence sabablaridan hosil bo‘ladigan kunlik xulosa.
3. **Real pilot yangi katta modullardan oldin turadi.** Keyingi funksiyalar real
   bog‘cha kuzatuvi va o‘lchanadigan muammoga asoslanadi.
4. **Payme/Click hozir bloklangan.** Merchant shartnomasi, yuridik shaxs,
   provider rekvizitlari va har bog‘cha uchun to‘lov modeli aniqlanmaguncha real
   pul integratsiyasi yozilmaydi.
5. **Hozir qurilmaydigan modullar:** oshxona 2-bosqichi, ta’lim LMS, biometrik
   xodim davomati, alohida native mobil ilova va talab bo‘lmasdan filial moduli.

---

## Bajarish tartibi

Har bir band alohida yakunlanadi: backup → kod → migration (kerak bo‘lsa) →
test → UI tekshiruv → hujjat yangilash. Keyingi band avvalgisi qabul mezonidan
o‘tmaguncha boshlanmaydi.

## 1. P0 — Attendance va CheckEvent invariantlari

### Muammo

QR check-in `Attendance`ni avtomatik yaratadi, ammo oddiy davomat sahifasi uni
mustaqil o‘zgartira yoki o‘chira oladi. Natijada `CheckEvent=IN`, lekin
`Attendance=ABSENT/yo‘q` holati paydo bo‘lishi mumkin. Billing Attendance’dan
foydalanadi.

### Ishlar

- `CheckEvent`ni kirish/chiqish bo‘yicha immutable source of truth deb belgilash;
- QR/manual check-in bir xil service orqali `CheckEvent(IN)` va kunlik
  `Attendance(PRESENT, arrived_at)` yaratishi;
- check-out `CheckEvent(OUT)` va `Attendance.left_at`ni atomar yangilashi;
- event bor kunda davomatdan `clear`ni bloklash;
- IN event bor kunda `ABSENT`ga o‘zgartirishni bloklash;
- OUT event bor kunda `PRESENT`/vaqtni buzadigan tahrirni bloklash;
- davomat ekranidagi qo‘lda “Keldi” imkoniyatini `method=manual` CheckEventga
  aylantirish yoki alohida aniq “faqat kunlik belgi” rejimini belgilash;
- mavjud bazada nomuvofiqlikni topadigan `audit_attendance_consistency` command;
- `--fix` rejimi faqat backupdan keyin, deterministik qoidalar bilan;
- billing faqat sinxronlashtirilgan Attendance summary’dan foydalanishini
  hujjatlashtirish.

### Qabul mezoni

- IN eventsiz `arrived_at` bo‘lishi mumkin emas (legacy istisno auditda chiqadi);
- IN eventli kunni absence/clear qilish mumkin emas;
- OUT event `left_at` bilan mos;
- QR va manual oqimdan keyin bir xil kunlik natija;
- parallel/takroriy request dublikat yaratmaydi;
- billing testi IN eventdan keyingi kunni present deb hisoblaydi.

### Testlar

- QR IN → Attendance avtomatik;
- manual IN → CheckEvent + Attendance;
- eventli kunni absent/clear qilish rad etiladi;
- check-outdan oldin IN shart;
- duplicate idempotency key;
- atomic rollback;
- consistency command dry-run va fix.

---

## 2. P0 — Multi-tenant hardening va bitta deployment

### Muammo

Model multi-tenant, ammo bitta o‘rnatmaga o‘tishdan oldin barcha global unique,
query scope, Telegram identity va fon vazifalari tenantlararo sinovdan o‘tishi
kerak.

### Joriy koddagi alohida xavflar

- invoice `number` global unique, lekin generator countni bog‘cha bo‘yicha oladi;
  ikkinchi bog‘chada bir xil `INV-YYYYMM-0001` collision beradi;
- `Payment(method, external_id)` global unique — alohida merchantlar bir xil
  provider ID bersa konflikt ehtimoli bor;
- `User.phone` global unique — bir direktor bir nechta bog‘chani boshqarsa hozir
  bitta User bir tenantga bog‘langan;
- `TelegramAccount.telegram_user_id` global unique va persons M2M — cross-tenant
  bog‘lanishni service darajasida qat’iy cheklash kerak;
- barcha Celery querylari tenant kesimida qayta audit qilinishi kerak;
- object ID bilan endpointlarga boshqa tenantdan kirish testlari to‘liq bo‘lishi kerak.

### Ishlar

- invoice raqamini tenant-prefiks bilan global unique qilish yoki
  `(kindergarten, number)` constraintga o‘tkazish;
- provider transaction unique scope’ini merchant/tenant bilan aniqlash;
- ko‘p bog‘chaga ega foydalanuvchi kerakmi — pilotda aniqlash; kerak bo‘lsa
  `UserKindergartenMembership`, aks holda global phone cheklovini hujjatlashtirish;
- Telegram account ↔ Person bog‘lanishida tenant invariant;
- har view/API/service/task uchun tenant matrix audit;
- cache/outbox/dedupe keylarda kindergarten ID;
- tenantlararo export, PDF va analytics isolation testlari;
- owner uchun bog‘cha almashtirish faqat membership modeli kerak bo‘lsa.

### Qabul mezoni

- bir bazada kamida 3 bog‘cha bir oyda invoice yarata oladi;
- bir tenant ikkinchisining hech bir obyektini ID orqali ko‘rmaydi/o‘zgartirmaydi;
- Telegram, PDF, Excel, search va Celery’da cross-tenant leak yo‘q;
- tenant backup/restore va tenantni export qilish strategiyasi hujjatda.

---

## 3. P0 — Pilot va operatsion tayyorgarlik

### Maqsad

Yangi featuredan oldin bitta real bog‘chada boshqariladigan pilot.

### Ishlar

- bitta pilot bog‘cha, mas’ul direktor/buxgalter/tarbiyachi topish;
- rozilik, ma’lumot maxfiyligi va support kanalini kelishish;
- demo yozuvlarsiz production-like muhit;
- kunlik avtomatik PostgreSQL backup;
- backupni alohida test bazaga tiklash (restore drill);
- error monitoring va health check;
- Celery/Redis/Django process supervision;
- Telegram failed outbox monitoring;
- 500 bola, 30 guruh, 12 oylik invoice/payment/davomat bilan load test;
- brauzer va eski Android/iOS Telegram Mini App device matrix;
- 2 hafta shadow/parallel operation;
- feedback va incident jurnalini yuritish.

### O‘lchanadigan metrikalar

- xodim onboarding vaqti;
- check-in uchun median vaqt;
- failed/offline scans;
- invoice yaratish va sahifa yuklanish vaqti;
- support murojaatlari;
- qarz yig‘ilish foizi;
- ma’lumot nomuvofiqligi;
- foydalanuvchi haftalik faolligi.

### Qabul mezoni

- restore amalda muvaffaqiyatli;
- 500 bolada kritik sahifalar kelishilgan limitda;
- pilotda P0 data-loss/security xato yo‘q;
- real foydalanuvchining top-10 muammosi yozilgan va prioritetlangan.

---

## 4. P1 — Excel orqali ma’lumot importi

### Nega yuqori prioritet?

100–300 bolani qo‘lda kiritish onboardingni to‘xtatadi. Import sotuv va ishga
tushirish jarayonining bir qismi.

### Birinchi versiya shabloni

- bola F.I.O.;
- tug‘ilgan sana, jins, ichki ID;
- ota-ona/kontakt F.I.O., telefon va kimligi;
- `can_pickup`, `is_payer`, `has_app_access`;
- guruh;
- tarif;
- chegirma (ixtiyoriy);
- shartnoma boshlanish sanasi;
- boshlang‘ich qarz yoki avans;
- allergiya/sog‘liq ogohlantirishi.

### Xavfsiz import oqimi

1. Standart `.xlsx` shablonni yuklab olish.
2. Fayl yuklash.
3. Faqat parse va preview — DBga yozmaslik.
4. Har qator uchun valid/error/warning.
5. Guruh/tarif/person duplicate takliflari.
6. Boshlang‘ich qarz va avansni boshqa maydonlardan alohida ko‘rsatish.
7. Operator tasdig‘i.
8. Bitta transaction yoki import batch bilan commit.
9. Natija: yaratildi/skipped/xato va downloadable report.
10. Audit log va import batch rollback strategiyasi.

### Muhim qoida

“AI import” keyingi qatlam: AI faqat ustun mapping va tozalashni taklif qiladi.
Odam previewni tasdiqlaydi. Pul summasi hech qachon yashirin avtomatik qaror bilan
yozilmaydi.

### Qabul mezoni

- 200 bola shablondan dublikatsiz import;
- bir xil faylni qayta yuklash nazoratli/idempotent;
- xato qatorlar sog‘lom qatorlarni jim buzmaydi;
- tenant isolation;
- boshlang‘ich balans audit qilinadi;
- formula/macro va zararli fayl himoyasi.

---

## 5. P1 — Hujjat yuklash va maxfiy storage

### Hujjat turlari

- shartnoma skani;
- tug‘ilganlik guvohnomasi;
- tibbiy ma’lumotnoma;
- pickup/favqulodda ruxsat hujjati;
- boshqa bola hujjati.

### Ishlar

- `ChildDocument` modeli: tenant, child, type, file, title, dates, uploader;
- private storage; public `/media/` link bermaslik;
- download endpointida tenant + permission tekshiruvi;
- PDF/JPEG/PNG allowlist, MIME va signature tekshiruvi;
- hajm limiti, tasodifiy storage key;
- productionda antivirus scan/quarantine;
- audit: upload/download/archive;
- versiya va amal qilish muddati;
- soft delete/archive va retention;
- backupda file storage ham bo‘lishi.

### Qabul mezoni

- boshqa tenant URL/ID bilan faylni ola olmaydi;
- ruxsatsiz tarbiyachi maxfiy hujjatni ko‘rmaydi;
- executable/fake MIME bloklanadi;
- arxivlangan hujjat tarixda qoladi;
- DB va object storage backup mosligi tekshiriladi.

---

## 6. P1 — Guruhdan guruhga ko‘chirish workflow’i

### Ishlar

- bola kartasida “Guruhga ko‘chirish” tugmasi;
- yangi guruh va kuchga kirish sanasi;
- yangi guruh standart tarifi yoki operator tanlovi;
- eski Enrollmentni yangi sana oldidan yopish;
- yangi Enrollment ochish;
- bir kunda overlap/gapni validatsiya qilish;
- yopilgan oy va mavjud invoice bilan to‘qnashuvni tushuntirish;
- transaction va audit;
- kelajak sanaga rejalashtirish.

### Qabul mezoni

- bir transactionda eski shartnoma yopilib yangisi ochiladi;
- davomat, invoice va tarix yo‘qolmaydi;
- guruh sig‘imi/reserv yangilanadi;
- xato bo‘lsa ikkala o‘zgarish ham rollback.

---

## 7. P1 — Oila/ikkinchi farzand chegirmasi

### Muhim tuzatish

Bu “bir kunlik ish” deb baholash optimistik. `Person` bir nechta bolaga ulanishi
texnik poydevor, lekin biznes qoidasi aniqlanmasdan avtomatik chegirma xavfli.

### Avval aniqlanadigan savollar

- qaysi kontakt oila identifikatori: payermi, ona/otami yoki householdmi;
- 2-, 3-farzand uchun foizlar;
- eng arzon/qimmat/yangi bolaga qo‘llanishi;
- bir bola chiqsa qayta hisoblash sanasi;
- tarixiy invoyslar o‘zgarmaydimi;
- boshqa chegirma bilan qo‘shiladimi;
- maksimum chegirma;
- admin override.

### Tavsiya

Aniq `Household` modeli yoki tasdiqlangan family link. Telefon yoki faqat bitta
Person orqali jim avtomatik oila deb qabul qilmaslik.

### Qabul mezoni

- preview operatorga kimga/nima sabab chegirma berilishini ko‘rsatadi;
- faqat kelajak invoyslariga ta’sir;
- tarixiy invoice line o‘zgarmaydi;
- audit va manual override mavjud.

---

## 8. P1 — Bandlik prognozi

### Mavjud ma’lumotlar

`capacity`, faol/reserved Enrollment, tugash sanasi, Application waitlist va
desired start.

### Ekran

- bugungi va keyingi 3/6 oy bandligi;
- guruh bo‘yicha mavjud/rezerv/navbat;
- rejalashtirilgan kirish/chiqish;
- yosh chegarasiga yaqinlashgan bolalar;
- “sentabrda 12 joy, navbatda 8” kabi xulosa;
- faqat ma’lumot yetarli bo‘lsa prognoz, aks holda warning.

### Qabul mezoni

- prognoz formulasining har soni drill-down qilinadi;
- application accepted bo‘lganda ikki marta sanalmaydi;
- kelajak Enrollment rezerv sifatida hisoblanadi;
- tenant va group filtrlari.

---

## 9. P1 — Churn va daromad yo‘qotilishi

### Ekran/metrikalar

- oyda ketgan bolalar;
- `end_reason` kesimi;
- bitirganlar alohida, salbiy churn alohida;
- guruh/tarif kesimi;
- yo‘qotilgan oylik recurring revenue;
- oldingi oylar bilan trend;
- sabab kiritilmagan shartnomalar warning’i.

### Qabul mezoni

- “bitirdi” biznes churn’dan alohida;
- yopilish sanasi bo‘yicha aniq hisob;
- drill-down bola ro‘yxatiga olib boradi;
- eksport qilinadi.

---

## 10. P1 — Ochiq qabul ariza formasi

### Ishlar

- login talab qilmaydigan branded forma;
- bog‘cha/tenantni subdomain yoki signed public slug orqali aniqlash;
- minimal ma’lumot va rozilik checkboxi;
- CSRF, rate limit, honeypot/CAPTCHA;
- duplicate telefon + bola bo‘yicha warning;
- Application yaratish va administratorga Telegram xabar;
- success sahifa, tracking source/UTM;
- maxfiy ma’lumotni URL/logga chiqarmaslik.

### Qabul mezoni

- bot/spamdan bazaviy himoya;
- bir tenant formasi boshqasiga lead yozmaydi;
- duplicate nazorat;
- mobile-friendly;
- admin xabari outbox orqali.

---

## 11. P2/BLOCKED — Payme/Click real integratsiyasi

### Nega hozir emas?

Oldingi biznes qaroriga ko‘ra karta/kvitansiya/provider qismi har bog‘cha uchun
merchant va yuridik shartlar aniqlanganda custom qilinadi. Provider hujjati,
test merchant va vakolat bo‘lmasa kod yozish taxminga aylanadi.

### Boshlash shartlari

- birinchi pilot bog‘chaning merchant shartnomasi;
- Payme yoki Click’ning rasmiy integration hujjati;
- test credential va callback domen;
- komissiya/refund/fiskal chek javobgarligi;
- merchant bitta platformanikimi yoki har tenantnikimi;
- privacy va accounting kelishuvi.

### Keyingi ishlar

- provider adapter interfeysi;
- invoice uchun payment link;
- imzolangan webhookni tekshirish;
- amount/currency/invoice/tenant matching;
- `(merchant, provider, external_id)` idempotency;
- `register_payment`ga ulash;
- refund/reversal va reconciliation;
- failed/unmatched payment navbati;
- Telegram “bir bosishda to‘lash” tugmasi;
- sandbox, duplicate, replay va forged webhook testlari.

### Qabul mezoni

- duplicate/replay pulni ikki marta yozmaydi;
- noto‘g‘ri summa/tenant avtomatik biriktirilmaydi;
- provider report bilan reconciliation;
- refund/storno auditda;
- secretlar faqat `.env`/secret managerda.

---

## 12. P2 — Pilotdan chiqqan top muammolar

Bu slot oldindan feature bilan to‘ldirilmaydi. Ikki haftalik real foydalanishdan
keyin frequency × severity × business impact bo‘yicha top muammolar shu yerga
qo‘yiladi. Misollar: eski telefon Mini App’ni ochmasligi, kamera permission,
internet uzilishi, noto‘g‘ri kalendar yoki xodimlar uchun noqulay oqim.

---

## Hozir qilinmaydigan ishlar

- oshxona 2-bosqichi: mavsumiy menyu, buyurtma, yaroqlilik muddati va brak jurnali;
- ta’lim kontenti/LMS;
- xodim biometrik check-in;
- alohida iOS/Android native ota-ona ilovasi;
- real talab bo‘lmasdan filial darajasidagi murakkab hierarchy;
- AI’ga moliyaviy summani tasdiqsiz yozdirish;
- real provider shartisiz payment integration;
- yangi modul qo‘shib, pilotni kechiktirish.

## Tavsiya etilgan vaqt ketma-ketligi

| Navbat | Ish | Taxminiy hajm | Bloklaydi/qaramlik |
|---:|---|---|---|
| 1 | Attendance/CheckEvent invariant | 2–4 kun | Data ishonchliligi |
| 2 | Multi-tenant hardening | 4–7 kun | Bitta SaaS deployment |
| 3 | Pilot operational readiness | 3–5 kun + 2 hafta kuzatuv | Real foydalanish |
| 4 | Excel import v1 | 5–8 kun | Tez onboarding |
| 5 | Private document upload | 5–8 kun | Qog‘ozni kamaytirish |
| 6 | Guruhga ko‘chirish | 1–3 kun | Operativ xato kamayishi |
| 7 | Family discount | 3–6 kun, qoida aniqlangach | Billing siyosati |
| 8 | Occupancy forecast | 2–4 kun | Egasi uchun rejalash |
| 9 | Churn analytics | 2–3 kun | Daromad nazorati |
| 10 | Public application | 3–5 kun | Lead generation |
| 11 | Payme/Click | tashqi shartlardan keyin 1–3 hafta | Merchant/provider |

Taxminlar kafolat emas; mavjud kod, integratsiya hujjati va pilot feedbackiga
qarab o‘zgaradi.

## Birinchi boshlanadigan vazifa

**#1 — Attendance va CheckEvent invariantlari.** Sababi bu mavjud real
ma’lumotning ishonchliligiga va billingga ta’sir qiladi. Yangi featuredan oldin
ikkita jadval orasidagi qarama-qarshilik yo‘li yopilishi kerak.
