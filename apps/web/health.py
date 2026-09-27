from datetime import timedelta

from django.conf import settings
from django.db import connection
from django.http import JsonResponse
from django.utils import timezone


def health(request):
    checks = {"database": False, "redis": False, "celery": False}
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            checks["database"] = cursor.fetchone()[0] == 1
    except Exception:
        pass
    try:
        import redis
        client = redis.Redis.from_url(settings.CELERY_BROKER_URL,
                                      socket_connect_timeout=1, socket_timeout=1)
        checks["redis"] = bool(client.ping())
    except Exception:
        pass
    try:
        from apps.operations.models import ServiceHeartbeat
        beat = ServiceHeartbeat.objects.filter(service="celery").first()
        checks["celery"] = bool(beat and beat.seen_at >= timezone.now() - timedelta(minutes=3))
    except Exception:
        pass
    ok = all(checks.values())
    return JsonResponse({"status": "ok" if ok else "degraded", "checks": checks},
                        status=200 if ok else 503)
