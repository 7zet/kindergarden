# Bu faqat demo ma'lumot. Real bog'chada ishlatmang.
import random
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import Permission
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.accounts.models import Role, User
from apps.attendance.models import Attendance, Status
from apps.billing.services import generate_invoices, month_start, register_payment
from apps.school.models import (BillingPolicy, Child, Contact, Discount, Enrollment,
                                Group, Kindergarten, Tariff)

from datetime import time

NAMES = [
    "Aliyev Sardor", "Karimova Zilola", "Rasulov Jasur", "Tursunova Malika",
    "Yusupov Bekzod", "Abdullayeva Nilufar", "Sobirov Aziz", "Nazarova Dilnoza",
    "Ergashev Otabek", "Qodirova Sevara", "Ismoilov Javohir", "Umarova Madina",
    "Xolmatov Sanjar", "Yo'ldosheva Gulnoza", "Mirzayev Doston",
    "Saidova Kamola", "To'xtayev Shohruh", "Rahimova Zarina",
]


class Command(BaseCommand):
    help = "Demo ma'lumot yaratadi"

    def handle(self, *args, **opts):
        if Kindergarten.objects.exists():
            self.stdout.write(self.style.WARNING("Ma'lumot allaqachon mavjud."))
            return

        kg = Kindergarten.objects.create(
            name="Quyoshcha bog'chasi", address="Toshkent sh.",
            phone="+998712001020")
        BillingPolicy.objects.create(kindergarten=kg)

        owner = User.objects.create_user(
            phone="+998901112233", password="admin123",
            full_name="Ahror Egasi", kindergarten=kg,
            is_owner=True, is_staff=True, is_superuser=True)

        teacher_role = Role.objects.create(kindergarten=kg, name="Tarbiyachi")
        teacher_role.permissions.set(Permission.objects.filter(codename__in=[
            "add_attendance", "change_attendance", "view_attendance"]))

        accountant = Role.objects.create(kindergarten=kg, name="Buxgalter")
        accountant.permissions.set(Permission.objects.filter(codename__in=[
            "view_all_groups", "view_child", "view_invoice", "add_invoice",
            "add_payment", "change_payment"]))

        director = Role.objects.create(kindergarten=kg, name="Direktor")
        director.permissions.set(Permission.objects.filter(codename__in=[
            "view_all_groups", "view_child", "add_child", "add_group",
            "view_invoice", "add_invoice", "add_payment", "change_payment",
            "add_attendance", "change_attendance", "change_billingpolicy"]))

        teacher = User.objects.create_user(
            phone="+998901112244", password="admin123",
            full_name="Nodira Tarbiyachi", kindergarten=kg, role=teacher_role)
        User.objects.create_user(
            phone="+998901112255", password="admin123",
            full_name="Gulnora Buxgalter", kindergarten=kg, role=accountant)

        t_yasli = Tariff.objects.create(
            kindergarten=kg, name="Yasli (2–3 yosh)",
            monthly_amount=Decimal("1500000"), valid_from=date(2026, 1, 1))
        t_bog = Tariff.objects.create(
            kindergarten=kg, name="Bog'cha (4–6 yosh)",
            monthly_amount=Decimal("1400000"), valid_from=date(2026, 1, 1))
        t_yarim = Tariff.objects.create(
            kindergarten=kg, name="Yarim kun",
            monthly_amount=Decimal("900000"), valid_from=date(2026, 1, 1))

        d2 = Discount.objects.create(
            kindergarten=kg, name="Ikkinchi farzand", percent=Decimal("15"))
        Discount.objects.create(
            kindergarten=kg, name="Xodim farzandi", percent=Decimal("50"))

        g1 = Group.objects.create(
            kindergarten=kg, name="1-guruh · Kichkintoylar",
            age_from=2, age_to=3, default_tariff=t_yasli,
            language=Group.Language.UZ, room_number="101",
            opens_at=time(8, 0), closes_at=time(18, 0))
        g2 = Group.objects.create(
            kindergarten=kg, name="2-guruh · Quyoshcha",
            age_from=4, age_to=5, default_tariff=t_bog,
            language=Group.Language.RU, room_number="203",
            opens_at=time(8, 0), closes_at=time(18, 0))
        g3 = Group.objects.create(
            kindergarten=kg, name="3-guruh · Bilimdon",
            age_from=5, age_to=6, default_tariff=t_bog,
            language=Group.Language.MIXED, room_number="204",
            opens_at=time(8, 0), closes_at=time(15, 0))

        g1.teachers.add(teacher)
        g2.teachers.add(teacher)
        g1.lead_teacher = teacher
        g1.save(update_fields=["lead_teacher"])
        g2.lead_teacher = teacher
        g2.save(update_fields=["lead_teacher"])

        today = timezone.localdate()
        start = month_start(today) - timedelta(days=70)
        start = month_start(start)

        groups = [(g1, t_yasli), (g2, t_bog), (g3, t_bog)]
        for i, name in enumerate(NAMES):
            group, tariff = groups[i % 3]
            if i % 7 == 0:
                tariff = t_yarim
            child = Child.objects.create(
                kindergarten=kg, full_name=name,
                birth_date=date(2026 - (3 + i % 4), 1 + i % 12, 1 + i % 27))
            Contact.objects.create(
                child=child, full_name=name.split()[0] + " ota-onasi",
                relation="Ota-ona", phone=f"+9989{random.randint(10000000, 99999999)}",
                kind=Contact.Kind.PARENT, is_primary=True, is_payer=True,
                can_pickup=True, has_app_access=True, can_see_billing=True,
                receives_messages=True)
            started = start if i % 5 else month_start(today) - timedelta(days=15)
            Enrollment.objects.create(
                child=child, group=group, tariff=tariff,
                discount=d2 if i % 6 == 0 else None,
                started_at=started)

        # Davomat: oxirgi 20 kun
        for enr in Enrollment.objects.all():
            for k in range(20):
                day = today - timedelta(days=k)
                if day.weekday() >= 5 or day < enr.started_at:
                    continue
                r = random.random()
                if r < 0.85:
                    st, reason = Status.PRESENT, ""
                elif r < 0.93:
                    st, reason = Status.ABSENT, "sick"
                else:
                    st, reason = Status.ABSENT, "unexcused"
                Attendance.objects.update_or_create(
                    enrollment=enr, day=day,
                    defaults={"status": st, "reason": reason, "marked_by": teacher})

        # Uch oy uchun invoys
        periods = []
        p = month_start(today)
        for _ in range(3):
            periods.append(p)
            p = month_start(p - timedelta(days=1))
        for period in reversed(periods):
            generate_invoices(kg, period)

        # To'lovlar: ba'zilar to'liq, ba'zilar qisman, ba'zilar umuman yo'q
        for i, child in enumerate(Child.objects.all()):
            if i % 5 == 4:
                continue
            enr = child.current_enrollment
            amount = enr.tariff.monthly_amount * (2 if i % 3 else 1)
            if i % 4 == 3:
                amount = amount / 2
            register_payment(
                kindergarten=kg, child=child, amount=amount,
                method=random.choice(["cash", "payme", "click"]),
                received_at=timezone.now() - timedelta(days=random.randint(1, 40)),
                user=owner)

        self.stdout.write(self.style.SUCCESS(
            "\nDemo ma'lumot tayyor.\n"
            "  Egasi:      +998901112233 / admin123\n"
            "  Buxgalter:  +998901112255 / admin123\n"
            "  Tarbiyachi: +998901112244 / admin123\n"))
