"""Eski shablonlardagi statik UI matnlarini to'liq tarjimaga o'tkazish ko'prigi.

Faqat ushbu oq ro'yxatdagi aniq matn tugunlari tarjima qilinadi. Shu sabab bola,
xodim, guruh nomlari va boshqa foydalanuvchi ma'lumotlari o'zgarmaydi.
Yangi kodda odatiy Django gettext ishlatiladi.
"""

import html as html_lib
import re

from django.utils.translation import get_language


RU = {
    "Sozlamalar": "Настройки", "Ish kunlari kalendari": "Календарь рабочих дней",
    "Audit jurnali": "Журнал аудита", "Bog'cha rekvizitlari": "Реквизиты детского сада",
    "Invoys, kvitansiya, shartnoma va dalolatnomalarda ko'rsatiladi.": "Указываются в счетах, квитанциях, договорах и актах.",
    "Rekvizitlarni saqlash": "Сохранить реквизиты", "Moliyaviy siyosat": "Финансовая политика",
    "Saqlash": "Сохранить", "Tariflar": "Тарифы", "+ Tarif": "+ Тариф",
    "Nomi": "Название", "Oylik": "Ежемесячно", "Amal qiladi": "Срок действия",
    "Holat": "Статус", "faol": "активен", "arxiv": "архив", "Tarif yo'q": "Тарифов нет",
    "Tarif tahrirlanmaydi. Narx o'zgarsa — yangi tarif qo'shing, eskisini nofaol qiling.": "Тариф не редактируется. При изменении цены добавьте новый тариф, а старый отключите.",
    "Chegirmalar": "Скидки", "+ Chegirma": "+ Скидка", "Foiz": "Процент",
    "Chegirma yo'q": "Скидок нет", "Kirish": "Вход", "Telefon": "Телефон", "Parol": "Пароль",
    "Telefon yoki parol noto'g'ri": "Неверный телефон или пароль",
    "Boshqaruv": "Панель управления", "Hisoblangan": "Начислено", "Yig'ilgan": "Собрано",
    "Umumiy qarz": "Общая задолженность", "Barcha davrlar bo'yicha": "За все периоды",
    "Bolalar": "Дети", "Eng eski qarzlar": "Самые старые задолженности", "Hammasi": "Все",
    "Bola": "Ребёнок", "Davr": "Период", "Qoldiq": "Остаток", "Qarzdorlar yo'q": "Должников нет",
    "Guruhlar": "Группы", "+ Bola": "+ Ребёнок", "Faol": "Активные", "Arxiv": "Архив",
    "Ism yoki telefon": "Имя или телефон", "Barcha guruhlar": "Все группы",
    "Barcha holatlar": "Все статусы", "Qabul qilingan": "Зачислен", "To'xtatilgan": "Приостановлен",
    "Filtrlash": "Фильтровать", "Yosh": "Возраст", "Guruh": "Группа", "Ota-ona": "Родитель",
    "Bola yo'q": "Детей нет", "+ Guruh": "+ Группа", "Bugun": "Сегодня",
    "Asosiy Tarbiyachilar": "Основной воспитатель", "xona": "комната", "Davomat": "Посещаемость",
    "Tabel": "Табель", "Tahrir": "Изменить", "Guruh yo'q": "Групп нет",
    "Orqaga": "Назад", "Yangi kontakt": "Новый контакт", "Kontakt": "Контакт",
    "Kirish / chiqish": "Приход / уход", "Arizalar": "Заявки", "+ Ariza": "+ Заявка",
    "Moliya": "Финансы", "Umumiy ko'rinish": "Обзор", "Umumiy ko‘rinish": "Обзор",
    "Invoyslar": "Счета", "To'lovlar": "Платежи", "To‘lovlar": "Платежи",
    "Qarzlar": "Задолженности", "Hisobotlar": "Отчёты", "Hisobot": "Отчёт",
    "Xarajatlar": "Расходы", "+ Xarajat": "+ Расход", "+ Kategoriya": "+ Категория",
    "+ Yetkazib beruvchi": "+ Поставщик", "Jami": "Итого", "Sana": "Дата",
    "Kategoriya": "Категория", "Yetkazib beruvchi": "Поставщик", "Usul": "Способ",
    "Summa": "Сумма", "Bekor": "Отменить", "Xarajat yo'q": "Расходов нет",
    "Kassa smenalari": "Кассовые смены", "Ochiq smena": "Открытая смена",
    "Boshlang'ich": "Начальный остаток", "Naqd tushum": "Наличные поступления",
    "Naqd xarajat": "Наличные расходы", "Kutilgan qoldiq": "Ожидаемый остаток",
    "Smenani yopish": "Закрыть смену", "Yangi smena": "Новая смена", "Smenani ochish": "Открыть смену",
    "Ochildi": "Открыта", "Kassir": "Кассир", "Yopildi": "Закрыта", "Kutilgan": "Ожидается",
    "Amaldagi": "Фактически", "Farq": "Разница", "Ish haqi": "Зарплата",
    "+ Xodim maoshi": "+ Оклад сотрудника", "Oyliklarni yaratish": "Сформировать зарплату",
    "Xodim": "Сотрудник", "Asosiy": "Основная", "Avans": "Аванс", "Bonus": "Премия",
    "Jarima": "Штраф", "Sof": "К выплате", "Maosh stavkalari": "Ставки зарплаты",
    "Telegram avtomatizatsiyasi": "Автоматизация Telegram", "E'lon yuborish": "Отправить объявление",
    "Navbatga qo'yish": "Поставить в очередь", "E'lonlar": "Объявления", "Vaqt": "Время",
    "Sarlavha": "Заголовок", "Oxirgi xabarlar": "Последние сообщения", "Yaratildi": "Создано",
    "Turi": "Тип", "Urinish": "Попытки", "Xato": "Ошибка", "Foydalanuvchilar": "Пользователи",
    "+ Foydalanuvchi": "+ Пользователь", "+ Rol": "+ Роль", "Rol": "Роль",
    "F.I.O.": "Ф.И.О.", "Faol emas": "Неактивен", "Kontakt shaxslar": "Контактные лица",
    "Qidirish": "Поиск", "Izoh": "Примечание", "To'lov usuli": "Способ оплаты",
    "To'langan vaqt": "Время оплаты", "Hujjat raqami": "Номер документа",
    "Xarajat nomi": "Наименование расхода", "To'lovchi": "Плательщик",
    "Olib ketishi mumkin": "Может забирать", "Kabinetga kirish": "Доступ к кабинету",
    "Moliyani ko'rish": "Просмотр финансов", "Xabar oladi": "Получает сообщения",
    "Asosiy aloqa": "Основной контакт", "Kimligi": "Кем приходится", "Mavjud shaxs": "Существующее лицо",
    "Yangi shaxs uchun F.I.O. majburiy": "Для нового лица обязательно Ф.И.О.",
    "Hech narsa topilmadi": "Ничего не найдено", "Oldingi": "Предыдущая", "Keyingi": "Следующая",
    "Yangi bola qo'shish": "Добавить ребёнка", "Invoyslarni chiqarish": "Выставить счета",
    "Yangi to'lov kiritish": "Внести новый платёж", "Guruhlar davomatini ochish": "Открыть посещаемость групп",
    "Kundalik ish": "Ежедневная работа", "Moliya hisobotlari": "Финансовые отчёты",
    "Bog'cha sozlamalari": "Настройки детского сада", "Tizim": "Система",
    "Bola kartasi": "Карточка ребёнка", "Aniqlanmagan to'lov": "Неидентифицированный платёж",
    "Invoys": "Счёт", "To'lov": "Платёж", "o'rin": "мест",
    "Bola, guruh, invoys yoki amalni yozing…": "Введите ребёнка, группу, счёт или действие…",
    "Natija topilmadi": "Ничего не найдено", "Boshqa so'z bilan qidiring": "Попробуйте другой запрос",
    "Boshqa so‘z bilan qidiring": "Попробуйте другой запрос",
    "tanlash": "выбор", "ochish": "открыть", "qidiruv": "поиск", "Global qidiruv": "Глобальный поиск",
    "Amalni tasdiqlang": "Подтвердите действие", "Qaytish": "Отмена", "Tasdiqlash": "Подтвердить",
    "Ruxsat yo'q": "Нет доступа", "Bosh sahifa": "Главная", "Sahifa topilmadi": "Страница не найдена",
    "Boshqaruvga qaytish": "Вернуться к панели", "Vaqtinchalik xatolik yuz berdi": "Произошла временная ошибка",
    "Hisoblangan ·": "Начислено ·", "Yig'ilgan ·": "Собрано ·", "invoys": "счёт",
    "Faol (18)": "Активные (18)", "Arxiv (0)": "Архив (0)", "Hammasi (19)": "Все (19)",
    "Tug'ilgan sana": "Дата рождения", "Jinsi": "Пол", "O'g'il": "Мальчик", "Qiz": "Девочка",
    "ID raqami": "Идентификатор", "Bo'sh qoldirilsa avtomatik beriladi.": "Если оставить пустым, будет создан автоматически.",
    "Manzil": "Адрес", "Shifokor": "Врач", "Shifokor telefoni": "Телефон врача", "Allergiya": "Аллергия",
    "Bola kartasida qizil ogohlantirish sifatida ko'rinadi.": "Отображается красным предупреждением в карточке ребёнка.",
    "Sog'liq haqida": "О здоровье", "Surunkali kasallik, doimiy dori, cheklovlar.": "Хронические заболевания, постоянные лекарства, ограничения.",
    "+ Shartnoma": "+ Договор", "Umumiy": "Общее", "Shartnomalar": "Договоры", "qarz": "долг",
    "Belgilanmagan": "Не отмечено", "Tug'ilgan": "Дата рождения", "Sog'liq va xavfsizlik": "Здоровье и безопасность",
    "Sog'liq izohi": "Примечание о здоровье", "Jins": "Пол", "Kontaktlar": "Контакты", "+ Kontakt": "+ Контакт",
    "Тип": "Тип", "Ruxsatlar": "Разрешения", "Amallar": "Действия", "asosiy": "основной",
    "to'lovchi": "плательщик", "olib ketadi": "может забирать", "kabinet": "кабинет", "moliya": "финансы",
    "O'chirish": "Удалить", "Qo'shimcha ma'lumot": "Дополнительная информация", "Tarif": "Тариф", "Chegirma": "Скидка",
    "davom etmoqda": "действует", "Shartnoma PDF": "Договор PDF", "To'xtatish": "Приостановить", "Yopish": "Закрыть",
    "Kirish / chiqish tarixi": "История прихода / ухода", "Amal": "Действие", "Check-in": "Приход", "Check-out": "Уход",
    "keldi": "пришёл", "Kasal": "Болезнь", "Kelmadi": "Не пришёл", "Oxirgi 60 kun": "Последние 60 дней",
    "Kech keldi": "Опоздал", "Sababsiz": "Без причины", "Keldi": "Пришёл", "Raqam": "Номер",
    "To'langan": "Оплачено", "Qisman to'langan": "Оплачено частично", "Taqsimlanmagan": "Не распределено",
    "Kvitansiya": "Квитанция", "Qarzdorlik dalolatnomasi PDF": "Акт задолженности PDF",
    "Joy bor": "Есть места", "Yosh (dan)": "Возраст от", "Yosh (gacha)": "Возраст до", "Sig'im": "Вместимость",
    "Maksimal nisbat (bola : tarbiyachi)": "Максимальное соотношение (дети : воспитатель)",
    "0 = tekshirilmaydi. Masalan 10 = bitta tarbiyachiga 10 tadan ko'p bola bo'lmasligi kerak.": "0 = без проверки. Например, 10 означает не более 10 детей на одного воспитателя.",
    "Standart tarif": "Стандартный тариф", "Ta'lim tili": "Язык обучения", "O'zbek": "Узбекский", "Rus": "Русский",
    "Ingliz": "Английский", "Aralash": "Смешанный", "Xona raqami": "Номер комнаты",
    "Ish boshlanishi": "Начало работы", "Ish tugashi": "Окончание работы", "Tarbiyachilar": "Воспитатели",
    "tarbiyachi": "воспитатель", "Tarbiyachi va yordamchi. Faqat shu ro'yxatdagilar guruh davomatini belgilay oladi.": "Воспитатель и помощник. Только сотрудники из этого списка могут отмечать посещаемость группы.",
    "Asosiy tarbiyachi": "Основной воспитатель", "Tarbiyachilar ro'yxatidan bittasi. Hisobot va mas'uliyat uchun.": "Один из воспитателей группы. Для отчётности и ответственности.",
    "Is active": "Активен", "Bugun keldi": "Сегодня пришли", "Yordamchilar": "Помощники", "Xona": "Комната",
    "Nisbat": "Соотношение", "Ish vaqti": "Рабочее время", "Yosh oralig'i": "Возрастной диапазон",
    "invoys yo'q": "счёта нет", "Tushgan to'lovlar": "Полученные платежи", "+ To'lov": "+ Платёж",
    "Barcha holat": "Все статусы", "Chiqarilgan": "Выставлен", "Bekor qilingan": "Отменён", "Ko'rsatish": "Показать",
    "Hisoblangan:": "Начислено:", "To'langan:": "Оплачено:", "Bu oy uchun invoys yo'q. Yuqoridagi tugmani bosing.": "За этот месяц счетов нет. Нажмите кнопку выше.",
    "Avansda": "Аванс", "Naqd": "Наличные", "Yangi to'lov": "Новый платёж", "Uzum": "Uzum",
    "Bank o'tkazmasi": "Банковский перевод", "Qabul qilindi": "Принято", "Jami:": "Итого:",
    "Muddat kelmagan": "Срок не наступил", "1–30 kun": "1–30 дней", "31–60 kun": "31–60 дней", "60+ kun": "60+ дней",
    "Kechikish": "Просрочка", "Dalolatnoma": "Акт", "Kengaytirilgan boshqaruv hisoboti": "Расширенный управленческий отчёт",
    "Oylar bo'yicha yig'ilish": "Сборы по месяцам", "Qarz": "Долг", "Guruhlar kesimi": "По группам",
    "Moliya va operatsiyalar": "Финансы и операции", "Reja": "План", "Tushum": "Доход", "ish haqi bilan": "включая зарплату",
    "Sof natija": "Чистый результат", "To'lov usullari": "Способы оплаты", "Operatsiya": "Операция",
    "Ma'lumot yo'q": "Нет данных", "Guruh rentabelligi": "Рентабельность групп",
    "Marja = guruhga tushgan to'lov − guruhga biriktirilgan bevosita xarajat. Umumiy xarajat va ish haqi alohida yuqorida hisoblangan.": "Маржа = платежи группы − прямые расходы группы. Общие расходы и зарплата рассчитаны отдельно выше.",
    "Bevosita xarajat": "Прямые расходы", "Marja": "Маржа", "Qarzdorlik dinamikasi": "Динамика задолженности",
    "Oy": "Месяц", "Hisobiy qarz": "Расчётная задолженность", "Davomat va kirish-chiqish": "Посещаемость и приход/уход",
    "Davomat belgilari": "Отметки посещаемости", "Davomat yo'q": "Нет посещаемости", "Yangi xarajat": "Новый расход",
    "Ta'lim materiallari": "Учебные материалы", "Oziq-ovqat": "Продукты", "Xo'jalik xarajatlari": "Хозяйственные расходы",
    "Boshqa xarajatlar": "Прочие расходы", "Ijara": "Аренда", "Kommunal to'lovlar": "Коммунальные платежи",
    "Karta": "Карта", "Ochiq": "Открыта", "Avval xodim maoshini kiriting va oyliklarni yarating.": "Сначала укажите оклады сотрудников и сформируйте зарплату.",
    "Xabar": "Сообщение", "Yuborish vaqti": "Время отправки",
    "Yuborildi": "Отправлено", "Rasmiy nomi": "Юридическое название", "Bank nomi": "Название банка",
    "Hisob raqami": "Расчётный счёт", "Oy o'rtasida kirish": "Поступление в середине месяца",
    "Kunlar bo'yicha": "По дням", "Yarim oy": "Половина месяца", "To'liq oy": "Полный месяц",
    "Oy o'rtasida chiqish": "Выбытие в середине месяца", "Butun oy kelmasa": "Если не посещал весь месяц",
    "Foiz bilan (joy saqlash)": "Процент (сохранение места)", "Joy saqlash foizi": "Процент сохранения места",
    "Chegara (kun)": "Порог (дни)", "Necha kundan kam kelsa 'butun oy kelmadi' hisoblanadi.": "Если посещено меньше указанного числа дней, считается отсутствием весь месяц.",
    "Invoys chiqadigan kun": "День выставления счёта", "To'lov muddati (kun)": "Срок оплаты (дни)",
    "Ortiqcha to'lov avansda": "Переплата учитывается как аванс", "Qabul xodimi": "Принимающий сотрудник",
    "Kunni bosib ish kuni / dam olish kunini almashtiring. Bayramlarni shu yerda belgilang — proratsiya shu kalendar bo'yicha hisoblanadi.": "Нажмите на дату, чтобы переключить рабочий/выходной день. Отметьте здесь праздники — пропорциональный расчёт ведётся по этому календарю.",
    "Ish kunlari:": "Рабочих дней:", "Barcha amallar": "Все действия", "Xodimlar oyligi": "Зарплата сотрудников",
    "Telefon faqat aloqa ma'lumoti; birlashtirish administrator tasdig'i bilan.": "Телефон используется только для связи; объединение выполняется с подтверждением администратора.",
    "Bir xil telefonli odamlar avtomatik birlashtirilmaydi. Faqat haqiqatdan bitta odam ekaniga ishonch hosil qilgach birlashtiring. Har bir bolaning olib ketish va moliya ruxsatlari alohida qoladi.": "Люди с одинаковым телефоном не объединяются автоматически. Объединяйте только убедившись, что это один человек. Разрешения на получение ребёнка и финансы остаются отдельными для каждого ребёнка.",
    "Shaxs": "Лицо", "Bolalar va ruxsatlar": "Дети и разрешения", "Birlashtirish": "Объединить",
    "Qaysi shaxsga...": "С каким лицом объединить...", "Yarim kun": "Полдня",
}

RU.update({
    "Boshqaruv paneli": "Панель управления",
    "Bugungi holat va moliyaviy ko'rsatkichlar": "Состояние на сегодня и финансовые показатели",
    "Hisoblangan reja": "Начислено по плану", "Yig'ilgan tushum": "Собрано платежей",
    "Bog'chadagi bolalar": "Дети в детском саду", "Nazorat talab qiladi": "Требует внимания",
    "Barcha davrlar": "За все периоды", "MOLIYA DINAMIKASI": "ФИНАНСОВАЯ ДИНАМИКА",
    "6 oylik moliyaviy dinamika": "Финансовая динамика за 6 месяцев",
    "BOLALAR HOLATI": "СОСТОЯНИЕ ДЕТЕЙ", "Umumiy tarkib": "Общий состав",
    "Ro'yxat": "Список", "Jami faol bazadagi bola": "Всего детей в активной базе",
    "Rezerv": "Резерв", "BUGUNGI DAVOMAT": "ПОСЕЩАЕМОСТЬ СЕГОДНЯ",
    "Jonli holat": "Текущие данные", "davomat": "посещаемость", "Keldi": "Пришли",
    "Kelmadi": "Не пришли", "Belgilanmagan": "Не отмечено", "Hozir ichkarida": "Сейчас внутри",
    "Bugungi davomat hali belgilanmagan": "Посещаемость за сегодня ещё не отмечена",
    "Kunlik holatni kiritgach statistika shu yerda ko'rinadi.": "После заполнения дневной посещаемости статистика появится здесь.",
    "Davomatni belgilash": "Отметить посещаемость", "SIG'IM VA QARZ": "ЗАПОЛНЕННОСТЬ И ДОЛГ",
    "Guruhlar holati": "Состояние групп", "Joy mavjud": "Есть места",
    "Deyarli to'liq": "Почти заполнено", "To'liq": "Заполнено",
    "NAZORAT TALAB QILADI": "ТРЕБУЕТ ВНИМАНИЯ", "Barcha qarzlar": "Все задолженности",
    "BOLA": "РЕБЁНОК", "INVOYS DAVRI": "ПЕРИОД СЧЁТА", "QOLDIQ": "ОСТАТОК",
    "AMAL": "ДЕЙСТВИЕ", "Ochish": "Открыть", "Batafsil hisobot": "Подробный отчёт",
    "Sozlashni yakunlang": "Завершите настройку", "qadam bajarildi": "шагов выполнено",
    "Oxirgi yangilanish": "Последнее обновление", "Tezkor qidiruv": "Быстрый поиск",
    "Zich rejim": "Компактный режим", "Odatiy rejim": "Обычный режим", "Yangi bola": "Новый ребёнок",
    "To'lov kiritish": "Внести платёж", "Umumiy qarzdorlik": "Общая задолженность",
    "ta invoys": "счетов", "bajarildi": "выполнено", "faol": "активны", "rezerv": "в резерве",
    "mln so'm": "млн сум", "so'm": "сум", "bola keldi": "детей пришло",
    "o'rin": "мест", "bo'sh": "свободно", "bola": "детей",
    "Barcha to'lovlar joyida": "Все платежи внесены", "Qarzlarni ko'rish": "Открыть задолженности",
    "guruhsiz": "без группы", "Guruhsiz": "Без группы", "Oy qoldig'i": "Остаток за месяц",
    "Grafik real invoys va to'lovlardan tuzilgan; qizil chiziq har oy invoyslarining qolgan qismini ko'rsatadi.": "График построен по фактическим счетам и платежам; красная линия показывает остаток по счетам каждого месяца.",
    "Grafik real invoys va to'lovlardan tuzilgan; kartalar": "График построен по фактическим счетам и платежам; карточки показывают",
    "oyini ko'rsatadi.": "месяц.", "Ro'yxat →": "Список →", "Hammasi →": "Все →", "Ochish →": "Открыть →",
})

CYR_OVERRIDES = {
    "Filtrlash": "Фильтрлаш",
    "Rus": "Рус",
    "Telegram xabarlar": "Telegram хабарлар",
}


CYR_OVERRIDES.update({
    "Boshqaruv paneli": "Бошқарув панели",
    "Bugungi holat va moliyaviy ko'rsatkichlar": "Бугунги ҳолат ва молиявий кўрсаткичлар",
    "Hisoblangan reja": "Ҳисобланган режа", "Yig'ilgan tushum": "Йиғилган тушум",
    "Bog'chadagi bolalar": "Боғчадаги болалар", "Nazorat talab qiladi": "Назорат талаб қилади",
    "Barcha davrlar": "Барча даврлар", "MOLIYA DINAMIKASI": "МОЛИЯ ДИНАМИКАСИ",
    "6 oylik moliyaviy dinamika": "6 ойлик молиявий динамика",
    "BOLALAR HOLATI": "БОЛАЛАР ҲОЛАТИ", "Umumiy tarkib": "Умумий таркиб",
    "Ro'yxat": "Рўйхат", "Jami faol bazadagi bola": "Жами фаол базадаги бола",
    "Rezerv": "Резерв", "BUGUNGI DAVOMAT": "БУГУНГИ ДАВОМАТ", "Jonli holat": "Жонли ҳолат",
    "davomat": "давомат", "Keldi": "Келди", "Kelmadi": "Келмади",
    "Belgilanmagan": "Белгиланмаган", "Hozir ichkarida": "Ҳозир ичкарида",
    "Bugungi davomat hali belgilanmagan": "Бугунги давомат ҳали белгиланмаган",
    "Kunlik holatni kiritgach statistika shu yerda ko'rinadi.": "Кунлик ҳолат киритилгач статистика шу ерда кўринади.",
    "Davomatni belgilash": "Давоматни белгилаш", "SIG'IM VA QARZ": "СИҒИМ ВА ҚАРЗ",
    "Guruhlar holati": "Гуруҳлар ҳолати", "Joy mavjud": "Жой мавжуд",
    "Deyarli to'liq": "Деярли тўлиқ", "To'liq": "Тўлиқ",
    "NAZORAT TALAB QILADI": "НАЗОРАТ ТАЛАБ ҚИЛАДИ", "Barcha qarzlar": "Барча қарзлар",
    "BOLA": "БОЛА", "INVOYS DAVRI": "ИНВОЙС ДАВРИ", "QOLDIQ": "ҚОЛДИҚ",
    "AMAL": "АМАЛ", "Ochish": "Очиш", "Batafsil hisobot": "Батафсил ҳисобот",
    "Sozlashni yakunlang": "Созлашни якунланг", "qadam bajarildi": "қадам бажарилди",
    "Oxirgi yangilanish": "Охирги янгиланиш", "Tezkor qidiruv": "Тезкор қидирув",
    "Zich rejim": "Зич режим", "Odatiy rejim": "Одатий режим", "Yangi bola": "Янги бола",
    "To'lov kiritish": "Тўлов киритиш", "Umumiy qarzdorlik": "Умумий қарздорлик",
    "ta invoys": "та инвойс", "bajarildi": "бажарилди", "faol": "фаол", "rezerv": "резерв",
    "mln so'm": "млн сўм", "so'm": "сўм", "bola keldi": "бола келди",
    "o'rin": "ўрин", "bo'sh": "бўш", "bola": "бола",
    "Barcha to'lovlar joyida": "Барча тўловлар жойида", "Qarzlarni ko'rish": "Қарзларни кўриш",
    "guruhsiz": "гуруҳсиз", "Guruhsiz": "Гуруҳсиз", "Oy qoldig'i": "Ой қолдиғи",
    "Grafik real invoys va to'lovlardan tuzilgan; qizil chiziq har oy invoyslarining qolgan qismini ko'rsatadi.": "График реал инвойс ва тўловлардан тузилган; қизил чизиқ ҳар ой инвойсларининг қолган қисмини кўрсатади.",
    "Grafik real invoys va to'lovlardan tuzilgan; kartalar": "График реал инвойс ва тўловлардан тузилган; карталар",
    "oyini ko'rsatadi.": "ойини кўрсатади.", "Ro'yxat →": "Рўйхат →", "Hammasi →": "Ҳаммаси →", "Ochish →": "Очиш →",
})


def _cyrillic(text):
    pairs = (
        ("O‘", "Ў"), ("O'", "Ў"), ("G‘", "Ғ"), ("G'", "Ғ"),
        ("o‘", "ў"), ("o'", "ў"), ("g‘", "ғ"), ("g'", "ғ"),
        ("Sh", "Ш"), ("Ch", "Ч"), ("Yo", "Ё"), ("Yu", "Ю"), ("Ya", "Я"),
        ("sh", "ш"), ("ch", "ч"), ("yo", "ё"), ("yu", "ю"), ("ya", "я"),
    )
    for latin, cyr in pairs:
        text = text.replace(latin, cyr)
    table = str.maketrans(
        "ABDEFGHIJKLMNOPQRSTUVXYZabdefghijklmnopqrstuvxyz",
        "АБДЕФГҲИЖКЛМНОПҚРСТУВХЙЗабдефгҳижклмнопқрстувхйз",
    )
    return text.translate(table)


def ui_text(text, language=None):
    """Return one UI label in the active language without requiring compiled .mo files."""
    language = (language or get_language() or "uz").lower()
    if language == "ru":
        return RU.get(text, text)
    if language.startswith("uz-cyrl"):
        return CYR_OVERRIDES.get(text, _cyrillic(text)) if text in RU else text
    return text


TEXT_NODE = re.compile(r">([^<>]+)<")
ATTR = re.compile(r'(?P<prefix>\b(?:placeholder|title|aria-label)=["\'])(?P<text>[^"\']+)(?P<suffix>["\'])')


def translate_html(html):
    language = (get_language() or "uz").lower()
    if language == "uz":
        return html

    def translate_exact(value):
        stripped = value.strip()
        source = html_lib.unescape(stripped)
        if not source or source not in RU:
            return value
        translated = ui_text(source, language)
        return value.replace(stripped, translated, 1)

    html = TEXT_NODE.sub(lambda m: ">" + translate_exact(m.group(1)) + "<", html)
    html = ATTR.sub(lambda m: m.group("prefix") + translate_exact(m.group("text")) + m.group("suffix"), html)
    if language == "ru":
        html = re.sub(r"(\d+) yosh(?: (\d+) oy)?", lambda m: f"{m.group(1)} лет" + (f" {m.group(2)} мес." if m.group(2) else ""), html)
        html = re.sub(r"(\d+) kun", r"\1 дней", html)
        html = re.sub(r"([А-Яа-яA-Za-z]+ \d{4}) uchun invoys chiqarish", r"Выставить счета за \1", html)
        html = re.sub(r"Hisoblangan ·", "Начислено ·", html)
        html = re.sub(r"Yig'ilgan ·", "Собрано ·", html)
        html = re.sub(r"(\d+) invoys", r"\1 счетов", html)
        html = re.sub(r"— davom etmoqda", "— действует", html)
        html = re.sub(r"— keldi", "— пришёл", html)
    elif language.startswith("uz-cyrl"):
        html = re.sub(r"(\d+) yosh(?: (\d+) oy)?", lambda m: f"{m.group(1)} ёш" + (f" {m.group(2)} ой" if m.group(2) else ""), html)
        html = re.sub(r"(\d+) kun", r"\1 кун", html)
        html = re.sub(r"Hisoblangan ·", "Ҳисобланган ·", html)
        html = re.sub(r"Yig'ilgan ·", "Йиғилган ·", html)
        html = re.sub(r"(\d+) invoys", r"\1 инвойс", html)
        html = re.sub(r" uchun invoys chiqarish", " учун инвойс чиқариш", html)
        html = re.sub(r"— davom etmoqda", "— давом этмоқда", html)
        html = re.sub(r"— keldi", "— келди", html)
    return html
