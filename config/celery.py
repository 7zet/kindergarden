import os

from celery import Celery
from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("bogcha")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

# settings.py JSON-serializable saqlanadi; Celery ishga tushganda crontabga aylanadi.
app.conf.beat_schedule["daily-business-automation"]["schedule"] = crontab(
    hour=18, minute=5
)
app.conf.beat_schedule["automatic-invoices-daily"]["schedule"] = crontab(
    hour=6, minute=0
)
