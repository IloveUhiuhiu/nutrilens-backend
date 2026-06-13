from drf_spectacular.utils import OpenApiParameter, OpenApiTypes, extend_schema
from rest_framework.decorators import api_view, permission_classes

from core.permissions import require_perm

from core.api import DEFAULT_ERROR_RESPONSES, api_response, handle_api_exceptions, validation_error_response
from .serializers import AdviceDateQuerySerializer, DateRangeQuerySerializer, OptionalDateRangeQuerySerializer
from .services import (
    admin_inference_metrics,
    admin_nutrition_metrics,
    admin_system_usage_metrics,
    admin_user_metrics,
    user_nutrition_advice,
    user_nutrition_summary,
    user_nutrition_trends,
)


@extend_schema(summary="Tổng quan dinh dưỡng", parameters=[OpenApiParameter("from", OpenApiTypes.DATE, required=True), OpenApiParameter("to", OpenApiTypes.DATE, required=True)], responses={200: OpenApiTypes.OBJECT, **DEFAULT_ERROR_RESPONSES})
@api_view(["GET"])
@permission_classes([require_perm("analysis.view_dailylog")])
@handle_api_exceptions
def nutrition_summary(request):
    """Chức năng: API thống kê dinh dưỡng user. Đầu vào: from/to. Đầu ra: tổng calories, macro, TDEE."""
    serializer = DateRangeQuerySerializer(data=request.query_params)
    if not serializer.is_valid():
        return validation_error_response(serializer)
    return api_response(
        "Nutrition summary retrieved successfully.",
        data=user_nutrition_summary(request.user, serializer.validated_data["date_from"], serializer.validated_data["date_to"]),
    )


@extend_schema(summary="Xu hướng dinh dưỡng", parameters=[OpenApiParameter("from", OpenApiTypes.DATE, required=True), OpenApiParameter("to", OpenApiTypes.DATE, required=True)], responses={200: OpenApiTypes.OBJECT, **DEFAULT_ERROR_RESPONSES})
@api_view(["GET"])
@permission_classes([require_perm("analysis.view_dailylog")])
@handle_api_exceptions
def nutrition_trends(request):
    """Chức năng: API xu hướng dinh dưỡng user. Đầu vào: from/to. Đầu ra: chuỗi dữ liệu theo ngày."""
    serializer = DateRangeQuerySerializer(data=request.query_params)
    if not serializer.is_valid():
        return validation_error_response(serializer)
    return api_response(
        "Nutrition trends retrieved successfully.",
        data=user_nutrition_trends(request.user, serializer.validated_data["date_from"], serializer.validated_data["date_to"]),
    )


@extend_schema(summary="Tư vấn dinh dưỡng", parameters=[OpenApiParameter("date", OpenApiTypes.DATE)], responses={200: OpenApiTypes.OBJECT, **DEFAULT_ERROR_RESPONSES})
@api_view(["GET"])
@permission_classes([require_perm("nutrients.view_healthadvicerule")])
@handle_api_exceptions
def nutrition_advice(request):
    """Chức năng: API tư vấn dinh dưỡng. Đầu vào: date tùy chọn. Đầu ra: mức cảnh báo và nội dung tư vấn."""
    serializer = AdviceDateQuerySerializer(data=request.query_params)
    if not serializer.is_valid():
        return validation_error_response(serializer)
    return api_response(
        "Nutrition advice retrieved successfully.",
        data=user_nutrition_advice(request.user, serializer.validated_data.get("date")),
    )


@extend_schema(summary="Admin dashboard người dùng", responses={200: OpenApiTypes.OBJECT, **DEFAULT_ERROR_RESPONSES})
@api_view(["GET"])
@permission_classes([require_perm("accounts.view_user")])
@handle_api_exceptions
def admin_users_dashboard(request):
    """Chức năng: API dashboard user admin. Đầu vào: request admin. Đầu ra: số user, active, staff, admin."""
    return api_response(
        "User dashboard metrics retrieved successfully.",
        data=admin_user_metrics(),
    )


@extend_schema(summary="Admin dashboard dinh dưỡng", parameters=[OpenApiParameter("from", OpenApiTypes.DATE), OpenApiParameter("to", OpenApiTypes.DATE)], responses={200: OpenApiTypes.OBJECT, **DEFAULT_ERROR_RESPONSES})
@api_view(["GET"])
@permission_classes([require_perm("analysis.view_dailylog")])
@handle_api_exceptions
def admin_nutrition_dashboard(request):
    """Chức năng: API dashboard dinh dưỡng admin. Đầu vào: from/to tùy chọn. Đầu ra: log count, meal count, totals."""
    serializer = OptionalDateRangeQuerySerializer(data=request.query_params)
    if not serializer.is_valid():
        return validation_error_response(serializer)
    return api_response(
        "Nutrition dashboard metrics retrieved successfully.",
        data=admin_nutrition_metrics(serializer.validated_data.get("date_from"), serializer.validated_data.get("date_to")),
    )


@extend_schema(summary="Admin dashboard inference", responses={200: OpenApiTypes.OBJECT, **DEFAULT_ERROR_RESPONSES})
@api_view(["GET"])
@permission_classes([require_perm("inference.view_inferencejob")])
@handle_api_exceptions
def admin_inference_dashboard(request):
    """Chức năng: API dashboard inference admin. Đầu vào: request admin. Đầu ra: job count, status, latency, feedback."""
    return api_response(
        "Inference dashboard metrics retrieved successfully.",
        data=admin_inference_metrics(),
    )


@extend_schema(summary="Admin dashboard sử dụng hệ thống", responses={200: OpenApiTypes.OBJECT, **DEFAULT_ERROR_RESPONSES})
@api_view(["GET"])
@permission_classes([require_perm("analysis.view_mealentry")])
@handle_api_exceptions
def admin_system_usage_dashboard(request):
    """Chức năng: API dashboard sử dụng hệ thống. Đầu vào: request admin. Đầu ra: meals theo nguồn và tổng sử dụng."""
    return api_response(
        "System usage metrics retrieved successfully.",
        data=admin_system_usage_metrics(),
    )
