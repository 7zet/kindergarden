from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.school.telegram import api_call


class Command(BaseCommand):
    help = "Telegram webhook manzilini Bot API orqali o'rnatadi"

    def handle(self, *args, **options):
        if not settings.TELEGRAM_BOT_TOKEN:
            raise CommandError("TELEGRAM_BOT_TOKEN kiritilmagan")
        if not settings.PUBLIC_BASE_URL.startswith("https://"):
            raise CommandError("Telegram webhook uchun PUBLIC_BASE_URL HTTPS bo'lishi kerak")
        payload = {
            "url": f"{settings.PUBLIC_BASE_URL}/telegram/webhook/",
            "allowed_updates": ["message"],
        }
        if settings.TELEGRAM_WEBHOOK_SECRET:
            payload["secret_token"] = settings.TELEGRAM_WEBHOOK_SECRET
        result = api_call("setWebhook", payload)
        if not result or not result.get("ok"):
            raise CommandError(f"Webhook o'rnatilmadi: {result}")
        self.stdout.write(self.style.SUCCESS("Telegram webhook o'rnatildi"))
