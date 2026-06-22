import logging

from rest_framework import status
from rest_framework.views import exception_handler

from .api import api_response

logger = logging.getLogger(__name__)


def api_exception_handler(exc, context):
    """Chức năng: chuẩn hóa exception DRF. Đầu vào: exception và context. Đầu ra: response envelope hoặc lỗi 500 chuẩn."""
    response = exception_handler(exc, context)
    if response is None:
        # DRF's own handler only recognizes APIException/Http404/PermissionDenied.
        # Anything else (e.g. a Redis connection error from a throttle/permission
        # check, which runs before any view-level try/except) would otherwise
        # re-escape past DRF entirely to Django's bare DEBUG=False error page —
        # a non-JSON body the mobile client can't parse, and silent (no console
        # log, since DEBUG=False also disables Django's console log handler).
        logger.exception("Unhandled non-DRF exception in %s", context.get("view"))
        return api_response(
            message="Internal server error.",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            errors={"detail": ["An unexpected error occurred."]},
        )

    detail = response.data
    message = "Request failed."

    if isinstance(detail, dict):
        raw_message = detail.get("detail")
        if raw_message:
            message = str(raw_message)
    elif isinstance(detail, list) and detail:
        message = str(detail[0])

    response.data = {
        "status_code": response.status_code,
        "message": message,
        "data": None,
        "errors": detail,
    }
    return response
