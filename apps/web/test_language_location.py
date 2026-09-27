import pytest
from django.utils import timezone
from datetime import datetime

from apps.accounts.models import User
from apps.billing.models import Payment
from apps.school.models import BillingPolicy, Child, Kindergarten


@pytest.fixture
def authenticated_client(db, client):
    kindergarten = Kindergarten.objects.create(name="Language UI test")
    BillingPolicy.objects.create(kindergarten=kindergarten)
    owner = User.objects.create_user(
        phone="+998909990091",
        password="test-pass",
        full_name="Egasi",
        kindergarten=kindergarten,
        is_owner=True,
    )
    client.force_login(owner)
    return client


def test_language_selector_is_in_account_and_removed_from_settings_card(authenticated_client):
    dashboard = authenticated_client.get("/?period=2026-09")
    assert dashboard.status_code == 200
    html = dashboard.content.decode()
    assert html.count('id="global-language-select"') == 1
    assert 'class="account-language"' in html
    assert 'class="chart-axis"' in html
    assert "Bugungi davomat hali belgilanmagan" in html
    assert 'class="donut"' not in html
    assert 'name="next" type="hidden" value="/?period=2026-09"' in html

    settings = authenticated_client.get("/settings/")
    assert settings.status_code == 200
    settings_html = settings.content.decode()
    assert settings_html.count('id="global-language-select"') == 1
    assert 'class="card language-settings"' not in settings_html


def test_dashboard_new_content_translates_to_russian_and_cyrillic(authenticated_client):
    authenticated_client.cookies["django_language"] = "ru"
    russian = authenticated_client.get("/").content.decode()
    assert "Панель управления" in russian
    assert "ФИНАНСОВАЯ ДИНАМИКА" in russian
    assert "Посещаемость за сегодня ещё не отмечена" in russian
    assert 'class="language-flag flag-ru"' in russian
    for untranslated in ("Tezkor qidiruv", "Yangi bola", "To'lov kiritish",
                         "Umumiy qarzdorlik", "Nazorat talab qiladi",
                         "Zich rejim", "Barcha davrlar"):
        assert untranslated not in russian

    authenticated_client.cookies["django_language"] = "uz-cyrl"
    cyrillic = authenticated_client.get("/").content.decode()
    assert "Бошқарув панели" in cyrillic
    assert "МОЛИЯ ДИНАМИКАСИ" in cyrillic
    assert "Бугунги давомат ҳали белгиланмаган" in cyrillic
    assert 'class="language-flag flag-uz"' in cyrillic
    assert "Тезкор қидирув" in cyrillic
    assert "Умумий қарздорлик" in cyrillic


def test_dashboard_month_income_uses_received_payments(authenticated_client):
    kindergarten = User.objects.get(phone="+998909990091").kindergarten
    Child.objects.create(kindergarten=kindergarten, full_name="Guruhsiz bola",
                         birth_date=datetime(2022, 1, 1).date())
    Payment.objects.create(
        kindergarten=kindergarten, amount=782600, method="cash",
        received_at=timezone.make_aware(datetime(2026, 9, 5, 10, 0)),
    )
    response = authenticated_client.get("/?period=2026-09")
    assert response.context["collected"] == 782600
    assert response.context["unassigned_count"] == 1
    assert response.context["children_count"] == (
        response.context["active_count"] + response.context["reserved_count"]
        + response.context["paused_count"] + response.context["unassigned_count"]
    )


@pytest.mark.parametrize("query, expected", [
    ("платеж", "Внести новый платёж"),
    ("ребенок", "Добавить ребёнка"),
    ("настройки", "Настройки детского сада"),
    ("отчет", "Финансовые отчёты"),
    ("посещаемость", "Открыть посещаемость групп"),
])
def test_global_search_supports_russian_actions(authenticated_client, query, expected):
    authenticated_client.cookies["django_language"] = "ru"
    response = authenticated_client.get(
        "/search/", {"q": query}, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
    assert response.status_code == 200
    assert expected in [item["title"] for item in response.json()["results"]]


def test_command_palette_ui_is_russian(authenticated_client):
    authenticated_client.cookies["django_language"] = "ru"
    html = authenticated_client.get("/").content.decode()
    assert "Введите ребёнка, группу, счёт или действие…" in html
    assert "Ничего не найдено" in html
    assert "Попробуйте другой запрос" in html
