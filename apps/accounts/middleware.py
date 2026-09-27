"""Joriy foydalanuvchini thread-local'da saqlaydi — audit uchun."""

import threading

from django.shortcuts import redirect

_state = threading.local()


def get_current_user():
    return getattr(_state, "user", None)


class CurrentUserMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        _state.user = getattr(request, "user", None)
        try:
            return self.get_response(request)
        finally:
            _state.user = None


class ForcePasswordChangeMiddleware:
    """Admin bergan vaqtinchalik parol bilan boshqa sahifalarni ochishni bloklaydi."""

    allowed_paths = ("/settings/account/password/", "/logout/", "/static/")

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if (user and user.is_authenticated and user.must_change_password
                and not request.path.startswith(self.allowed_paths)):
            return redirect("own_password_change")
        return self.get_response(request)
