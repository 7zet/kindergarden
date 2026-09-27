"""Audit yozuvi. Har bir moliyaviy o'zgarish shu yerdan o'tadi."""

import logging

from .middleware import get_current_user

logger = logging.getLogger("apps.audit")


def log(action, obj, note="", before=None, after=None, user=None):
    """Audit yozuvi qo'shadi. Hech qachon asosiy amalni to'xtatmaydi."""
    from .models import AuditLog
    try:
        u = user or get_current_user()
        if u is not None and not getattr(u, "is_authenticated", False):
            u = None
        AuditLog.objects.create(
            user=u,
            action=action,
            object_type=obj.__class__.__name__,
            object_id=str(getattr(obj, "pk", "")),
            note=note,
            before=before,
            after=after,
        )
    except Exception:
        logger.exception("Audit yozuvi saqlanmadi: %s %s", action, obj)
