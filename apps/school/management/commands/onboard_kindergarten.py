from django.contrib.auth.models import Permission
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.accounts.models import Role, User
from apps.school.models import BillingPolicy, Kindergarten


ROLE_PERMISSIONS = {
    "Direktor": [
        "view_invoice", "add_invoice", "add_payment", "view_child", "add_child",
        "add_group", "add_attendance", "view_all_groups", "change_billingpolicy",
        "add_user", "view_application", "add_application",
        "check_in_child", "check_out_child", "manual_check_child",
        "override_check_child",
    ],
    "Buxgalter": [
        "view_invoice", "add_invoice", "add_payment", "view_child",
        "view_all_groups", "view_application",
    ],
    "Tarbiyachi": ["view_child", "add_attendance", "check_in_child", "check_out_child"],
    "Qabul xodimi": [
        "view_child", "view_all_groups", "check_in_child", "check_out_child",
        "manual_check_child",
    ],
}


class Command(BaseCommand):
    help = "Yangi bog'cha, moliyaviy siyosat, standart rollar va egasini yaratadi"

    def add_arguments(self, parser):
        parser.add_argument("--name", required=True, help="Bog'cha nomi")
        parser.add_argument("--owner-name", required=True, help="Egasi F.I.O.")
        parser.add_argument("--owner-phone", required=True, help="Egasi telefoni")
        parser.add_argument("--password", required=True, help="Boshlang'ich parol")
        parser.add_argument("--address", default="")
        parser.add_argument("--phone", default="", help="Bog'cha telefoni")

    @transaction.atomic
    def handle(self, *args, **options):
        if User.objects.filter(phone=options["owner_phone"]).exists():
            raise CommandError("Bu telefon bilan foydalanuvchi allaqachon mavjud")
        if len(options["password"]) < 8:
            raise CommandError("Parol kamida 8 belgidan iborat bo'lishi kerak")

        kg = Kindergarten.objects.create(
            name=options["name"], address=options["address"], phone=options["phone"]
        )
        BillingPolicy.objects.create(kindergarten=kg)
        for role_name, codenames in ROLE_PERMISSIONS.items():
            role = Role.objects.create(kindergarten=kg, name=role_name, is_system=True)
            role.permissions.set(Permission.objects.filter(codename__in=codenames))
        User.objects.create_user(
            phone=options["owner_phone"], password=options["password"],
            full_name=options["owner_name"], kindergarten=kg, is_owner=True,
        )
        self.stdout.write(self.style.SUCCESS(
            f"'{kg.name}' tayyor: siyosat, 3 rol va egasi yaratildi."
        ))
