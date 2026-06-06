from functools import wraps
import logging

from drf_spectacular.utils import inline_serializer
from rest_framework import serializers, status
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


logger = logging.getLogger(__name__)


API_ERROR_RESPONSE = inline_serializer(
    name="CoreApiErrorResponse",
    fields={
        "status_code": serializers.IntegerField(),
        "message": serializers.CharField(),
        "data": serializers.JSONField(allow_null=True),
        "errors": serializers.JSONField(allow_null=True),
    },
)


API_EMPTY_RESPONSE = inline_serializer(
    name="CoreApiEmptyResponse",
    fields={
        "status_code": serializers.IntegerField(),
        "message": serializers.CharField(),
        "data": serializers.JSONField(allow_null=True),
        "errors": serializers.JSONField(allow_null=True),
    },
)


DEFAULT_ERROR_RESPONSES = {
    400: API_ERROR_RESPONSE,
    401: API_ERROR_RESPONSE,
    403: API_ERROR_RESPONSE,
    404: API_ERROR_RESPONSE,
    502: API_ERROR_RESPONSE,
    503: API_ERROR_RESPONSE,
    504: API_ERROR_RESPONSE,
    500: API_ERROR_RESPONSE,
}


def api_response(message, status_code=status.HTTP_200_OK, data=None, errors=None):
    """Chức năng: tạo response chuẩn. Đầu vào: message, status_code, data, errors. Đầu ra: DRF Response."""
    return Response(
        {
            "status_code": status_code,
            "message": message,
            "data": data,
            "errors": errors,
        },
        status=status_code,
    )


def validation_error_response(serializer):
    """Chức năng: trả lỗi validation. Đầu vào: serializer không hợp lệ. Đầu ra: response 400 chuẩn."""
    return api_response(
        message="Validation failed.",
        status_code=status.HTTP_400_BAD_REQUEST,
        errors=serializer.errors,
    )


def not_found_response(message="Resource not found.", field="id"):
    """Chức năng: trả lỗi không tìm thấy. Đầu vào: message và field lỗi. Đầu ra: response 404 chuẩn."""
    return api_response(
        message=message,
        status_code=status.HTTP_404_NOT_FOUND,
        errors={field: [message]},
    )


def external_service_error_response(exc, service_name="external_api"):
    """Chức năng: trả lỗi API ngoài chuẩn. Đầu vào: exception service. Đầu ra: response lỗi phù hợp."""
    status_code = getattr(exc, "status_code", status.HTTP_502_BAD_GATEWAY)
    code = getattr(exc, "code", "external_api_error")
    message = getattr(exc, "public_message", str(exc))
    return api_response(
        message=f"{service_name} request failed.",
        status_code=status_code,
        errors={service_name: [{"code": code, "message": message}]},
    )


def handle_api_exceptions(view_func):
    """Chức năng: bọc API để bắt lỗi ngoài dự kiến. Đầu vào: view function. Đầu ra: wrapper trả response chuẩn."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        """Chức năng: thực thi view có bắt lỗi. Đầu vào: request và args. Đầu ra: response chuẩn."""
        try:
            return view_func(request, *args, **kwargs)
        except Exception as exc:
            logger.exception("Unhandled API error in %s", view_func.__name__)
            return api_response(
                message="Internal server error.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                errors={"detail": ["An unexpected error occurred."]},
            )

    return wrapper


def paginate_queryset(request, queryset, serializer_class, page_size=20):
    """Chức năng: phân trang queryset. Đầu vào: request, queryset, serializer, page_size. Đầu ra: dữ liệu page."""
    paginator = PageNumberPagination()
    paginator.page_size = page_size
    page = paginator.paginate_queryset(queryset, request)
    serializer = serializer_class(page, many=True, context={"request": request})
    paginated = paginator.get_paginated_response(serializer.data)
    return paginated.data
