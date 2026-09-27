from django.contrib import admin
from django.urls import include, path
from apps.web import telegram_views
from apps.web.health import health

urlpatterns = [
    path("health/", health, name="health"),
    path("i18n/", include("django.conf.urls.i18n")),
    path("admin/", admin.site.urls),
    path("telegram/webhook/", telegram_views.webhook, name="telegram_webhook"),
    path("telegram/pickup/<uuid:token>/", telegram_views.pickup_qr, name="pickup_qr"),
    path("telegram/mini/", telegram_views.mini_app, name="telegram_mini_app"),
    path("telegram/mini/session/", telegram_views.mini_session, name="telegram_mini_session"),
    path("telegram/contact-qr/", telegram_views.contact_qr, name="telegram_contact_qr"),
    path("telegram/parent/credential/", telegram_views.parent_credential, name="parent_credential"),
    path("telegram/staff/", telegram_views.staff_mini_app, name="telegram_staff_app"),
    path("telegram/staff/resolve/", telegram_views.staff_resolve, name="staff_resolve"),
    path("telegram/staff/confirm/", telegram_views.staff_confirm, name="staff_confirm"),
    path("telegram/staff/bootstrap/", telegram_views.staff_bootstrap, name="staff_bootstrap"),
    path("finance/", include("apps.operations.urls")),
    path("kitchen/", include("apps.kitchen.urls")),
    path("", include("apps.web.urls")),
]

handler403 = "apps.web.errors.permission_denied"
handler404 = "apps.web.errors.page_not_found"
handler500 = "apps.web.errors.server_error"
