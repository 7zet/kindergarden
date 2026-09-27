from .ui_translation import translate_html


class LegacyUiTranslationMiddleware:
    """Gettext'ga bosqichma-bosqich ko'chayotgan HTML uchun xavfsiz ko'prik."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        content_type = response.get("Content-Type", "")
        if (response.status_code < 400 and "text/html" in content_type
                and not getattr(response, "streaming", False)):
            charset = response.charset or "utf-8"
            html = response.content.decode(charset)
            translated = translate_html(html)
            if translated != html:
                response.content = translated.encode(charset)
                response["Content-Length"] = str(len(response.content))
        return response
