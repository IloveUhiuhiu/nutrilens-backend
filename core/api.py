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
    500: API_ERROR_RESPONSE,
}


def api_response(message, status_code=status.HTTP_200_OK, data=None, errors=None):
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
    return api_response(
        message="Validation failed.",
        status_code=status.HTTP_400_BAD_REQUEST,
        errors=serializer.errors,
    )


def not_found_response(message="Resource not found.", field="id"):
    return api_response(
        message=message,
        status_code=status.HTTP_404_NOT_FOUND,
        errors={field: [message]},
    )


def handle_api_exceptions(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        try:
            return view_func(request, *args, **kwargs)
        except Exception as exc:
            logger.exception("Unhandled API error in %s", view_func.__name__)
            return api_response(
                message="Internal server error.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                errors={"detail": [str(exc)]},
            )

    return wrapper


def paginate_queryset(request, queryset, serializer_class, page_size=20):
    paginator = PageNumberPagination()
    paginator.page_size = page_size
    page = paginator.paginate_queryset(queryset, request)
    serializer = serializer_class(page, many=True, context={"request": request})
    paginated = paginator.get_paginated_response(serializer.data)
    return paginated.data
