"""Oylik invoyslarni chiqaradi. Cron orqali har kuni ishga tushiriladi:

    0 6 * * * cd /srv/bogcha && .venv/bin/python manage.py run_billing

Faqat siyosatdagi `invoice_generation_day` kelganda ishlaydi.
Idempotent — kuniga bir necha marta chaqirilsa ham dublikat chiqmaydi.
"""

import logging

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.billing.services import generate_invoices, month_start
from apps.school.models import Kindergarten

logger = logging.getLogger("apps.billing")


class Command(BaseCommand):
    help = "Oylik invoyslarni avtomatik chiqaradi"

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true",
                            help="Generatsiya kunini tekshirmasdan ishga tushirish")
        parser.add_argument("--period", help="YYYY-MM formatida")

    def handle(self, *args, **opts):
        today = timezone.localdate()
        for kg in Kindergarten.objects.filter(is_active=True).select_related("policy"):
            policy = getattr(kg, "policy", None)
            if policy is None:
                continue
            if not opts["force"] and today.day != policy.invoice_generation_day:
                continue

            if opts["period"]:
                y, m = opts["period"].split("-")
                period = month_start(today.replace(year=int(y), month=int(m), day=1))
            else:
                period = month_start(today)

            result = generate_invoices(kg, period)
            msg = (f"{kg.name} — {period:%m.%Y}: "
                   f"{result['created']} yaratildi, {result['skipped']} mavjud")
            logger.info(msg)
            self.stdout.write(self.style.SUCCESS(msg))
