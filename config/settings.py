"""Sozlamalar. Maxfiy qiymatlar .env faylda (repozitoriyga tushmaydi)."""

from pathlib import Path
from django.core.exceptions import ImproperlyConfigured

from decouple import Csv, config

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = config("SECRET_KEY", default="dev-only-insecure-key")
DEBUG = config("DJANGO_DEBUG", default=False, cast=bool)
ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="localhost,127.0.0.1", cast=Csv())
CSRF_TRUSTED_ORIGINS = config("CSRF_TRUSTED_ORIGINS", default="", cast=Csv())

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "apps.accounts",
    "apps.school",
    "apps.attendance",
    "apps.billing",
    "apps.operations",
    "apps.kitchen",
    "apps.web",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "apps.accounts.middleware.ForcePasswordChangeMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.accounts.middleware.CurrentUserMiddleware",
    "apps.web.i18n_middleware.LegacyUiTranslationMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [BASE_DIR / "templates"],
    "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
    ]},
}]

WSGI_APPLICATION = "config.wsgi.application"

# PostgreSQL yagona qo'llab-quvvatlanadigan ma'lumotlar bazasi. Kerakli
# rekvizitlardan bittasi yo'q bo'lsa, ilova bo'sh lokal bazaga jimgina o'tib
# ketmasdan ishga tushishda xato beradi.
DATABASES = {"default": {
    "ENGINE": "django.db.backends.postgresql",
    "NAME": config("DB_NAME"),
    "USER": config("DB_USER"),
    "PASSWORD": config("DB_PASSWORD"),
    "HOST": config("DB_HOST", default="127.0.0.1"),
    "PORT": config("DB_PORT", default="5432"),
    "CONN_MAX_AGE": 60,
    "CONN_HEALTH_CHECKS": True,
    "ATOMIC_REQUESTS": True,
    "OPTIONS": {
        "sslmode": config(
            "DB_SSLMODE", default="prefer" if DEBUG else "require"
        ),
    },
}}

AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "uz"
LANGUAGES = [
    ("uz", "O‘zbekcha"),
    ("uz-cyrl", "Ўзбекча"),
    ("ru", "Русский"),
]
LOCALE_PATHS = [BASE_DIR / "locale"]
TIME_ZONE = config("TIME_ZONE", default="Asia/Tashkent")
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/login/"

PAGE_SIZE = config("PAGE_SIZE", default=50, cast=int)
APP_VERSION = config("APP_VERSION", default="1.5.0")
TELEGRAM_BOT_TOKEN = config("TELEGRAM_BOT_TOKEN", default="")
TELEGRAM_BOT_USERNAME = config("TELEGRAM_BOT_USERNAME", default="")
TELEGRAM_WEBHOOK_SECRET = config("TELEGRAM_WEBHOOK_SECRET", default="")
PUBLIC_BASE_URL = config("PUBLIC_BASE_URL", default="http://127.0.0.1:8000").rstrip("/")
TELEGRAM_MINI_APP_URL = config(
    "TELEGRAM_MINI_APP_URL", default=f"{PUBLIC_BASE_URL}/telegram/mini/"
)
TELEGRAM_STAFF_APP_URL = config(
    "TELEGRAM_STAFF_APP_URL", default=f"{PUBLIC_BASE_URL}/telegram/staff/"
)

CELERY_BROKER_URL = config("CELERY_BROKER_URL", default="redis://127.0.0.1:6379/0")
CELERY_RESULT_BACKEND = config("CELERY_RESULT_BACKEND", default="redis://127.0.0.1:6379/1")
CELERY_TASK_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_BEAT_SCHEDULE = {
    "worker-heartbeat-every-minute": {
        "task": "apps.operations.tasks.record_worker_heartbeat",
        "schedule": 60.0,
    },
    "telegram-outbox-every-minute": {
        "task": "apps.operations.tasks.deliver_notification_outbox",
        "schedule": 60.0,
    },
    "scheduled-announcements-every-minute": {
        "task": "apps.operations.tasks.queue_scheduled_announcements",
        "schedule": 60.0,
    },
    "automatic-invoices-daily": {
        "task": "apps.operations.tasks.automatic_invoice_generation",
        "schedule": {"__type__": "crontab", "hour": 6, "minute": 0},
    },
    "daily-business-automation": {
        "task": "apps.operations.tasks.daily_business_automation",
        "schedule": {"__type__": "crontab", "hour": 18, "minute": 5},
    },
}

SENTRY_DSN = config("SENTRY_DSN", default="")
if SENTRY_DSN:
    import sentry_sdk
    sentry_sdk.init(dsn=SENTRY_DSN, send_default_pii=False,
                    traces_sample_rate=config("SENTRY_TRACES_SAMPLE_RATE", default=0.05, cast=float),
                    environment=config("SENTRY_ENVIRONMENT", default="production"))

# Xavfsizlik — faqat productionda yoqiladi
if not DEBUG:
    if SECRET_KEY == "dev-only-insecure-key" or len(SECRET_KEY) < 32:
        raise ImproperlyConfigured("Production uchun kamida 32 belgili SECRET_KEY kerak")
    if not ALLOWED_HOSTS or "*" in ALLOWED_HOSTS:
        raise ImproperlyConfigured("Productionda ALLOWED_HOSTS aniq domenlardan iborat bo'lishi kerak")
    SECURE_SSL_REDIRECT = config("SECURE_SSL_REDIRECT", default=True, cast=bool)
    COOKIE_SECURE = config("COOKIE_SECURE", default=True, cast=bool)
    SESSION_COOKIE_SECURE = COOKIE_SECURE
    CSRF_COOKIE_SECURE = COOKIE_SECURE
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_REFERRER_POLICY = "same-origin"
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    X_FRAME_OPTIONS = "DENY"
    SESSION_COOKIE_HTTPONLY = True
    SESSION_EXPIRE_AT_BROWSER_CLOSE = True
    SESSION_COOKIE_SAMESITE = "Lax"
    CSRF_COOKIE_SAMESITE = "Lax"
    SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"

LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"simple": {"format": "{levelname} {asctime} {name} {message}",
                              "style": "{"}},
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "simple"},
        "file": {"class": "logging.handlers.RotatingFileHandler",
                 "filename": LOG_DIR / "app.log",
                 "maxBytes": 5 * 1024 * 1024, "backupCount": 5,
                 "formatter": "simple"},
    },
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "apps": {"handlers": ["console", "file"], "level": "INFO", "propagate": False},
        "django.request": {"handlers": ["console", "file"], "level": "ERROR",
                           "propagate": False},
    },
}
(BASE_DIR / "logs").mkdir(exist_ok=True)
