from django.db.models import Avg, Count, Sum
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, OpenApiTypes, extend_schema
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser, IsAuthenticated

from accounts.models import User
from analysis.models import DailyLog, MealEntry
from core.api import DEFAULT_ERROR_RESPONSES, api_response, handle_api_exceptions
from inference.models import InferenceFeedback, InferenceJob
from nutrients.models import HealthAdviceRule


def require_date_range(request):
    date_from = request.query_params.get("from")
    date_to = request.query_params.get("to")
    if not date_from or not date_to:
        return None, None, api_response(
            "Missing date range.",
            status_code=status.HTTP_400_BAD_REQUEST,
            errors={"date_range": ["Both from and to are required."]},
        )
    return date_from, date_to, None


def log_totals(queryset):
    totals = queryset.aggregate(
        total_calories=Sum("total_calories"),
        total_protein=Sum("total_protein"),
        total_carbs=Sum("total_carbs"),
        total_fat=Sum("total_fat"),
        total_weight=Sum("total_weight"),
        average_calories=Avg("total_calories"),
    )
    return {key: round(value or 0, 2) for key, value in totals.items()}


@extend_schema(parameters=[OpenApiParameter("from", OpenApiTypes.DATE, required=True), OpenApiParameter("to", OpenApiTypes.DATE, required=True)], responses={200: OpenApiTypes.OBJECT, **DEFAULT_ERROR_RESPONSES})
@api_view(["GET"])
@permission_classes([IsAuthenticated])
@handle_api_exceptions
def nutrition_summary(request):
    date_from, date_to, error = require_date_range(request)
    if error:
        return error
    logs = DailyLog.objects.filter(user=request.user, date__gte=date_from, date__lte=date_to)
    return api_response(
        "Nutrition summary retrieved successfully.",
        data={
            "from": date_from,
            "to": date_to,
            "tdee": request.user.tdee,
            "totals": log_totals(logs),
            "days": logs.count(),
        },
    )


@extend_schema(parameters=[OpenApiParameter("from", OpenApiTypes.DATE, required=True), OpenApiParameter("to", OpenApiTypes.DATE, required=True)], responses={200: OpenApiTypes.OBJECT, **DEFAULT_ERROR_RESPONSES})
@api_view(["GET"])
@permission_classes([IsAuthenticated])
@handle_api_exceptions
def nutrition_trends(request):
    date_from, date_to, error = require_date_range(request)
    if error:
        return error
    logs = DailyLog.objects.filter(user=request.user, date__gte=date_from, date__lte=date_to).order_by("date")
    return api_response(
        "Nutrition trends retrieved successfully.",
        data=[
            {
                "date": log.date,
                "calories": log.total_calories,
                "protein": log.total_protein,
                "carbs": log.total_carbs,
                "fat": log.total_fat,
                "weight": log.total_weight,
                "tdee_percent": round((log.total_calories / request.user.tdee * 100), 2) if request.user.tdee else 0,
            }
            for log in logs
        ],
    )


@extend_schema(parameters=[OpenApiParameter("date", OpenApiTypes.DATE)], responses={200: OpenApiTypes.OBJECT, **DEFAULT_ERROR_RESPONSES})
@api_view(["GET"])
@permission_classes([IsAuthenticated])
@handle_api_exceptions
def nutrition_advice(request):
    date = request.query_params.get("date") or timezone.localdate()
    log = DailyLog.objects.filter(user=request.user, date=date).first()
    percent = round((log.total_calories / request.user.tdee * 100), 2) if log and request.user.tdee else 0
    rule = HealthAdviceRule.objects.filter(min_percent__lte=percent, max_percent__gte=percent).first()
    return api_response(
        "Nutrition advice retrieved successfully.",
        data={
            "date": date,
            "tdee_percent": percent,
            "alert_level": rule.alert_level if rule else "normal",
            "advice_content": rule.advice_content if rule else "",
        },
    )


@extend_schema(responses={200: OpenApiTypes.OBJECT, **DEFAULT_ERROR_RESPONSES})
@api_view(["GET"])
@permission_classes([IsAdminUser])
@handle_api_exceptions
def admin_users_dashboard(request):
    return api_response(
        "User dashboard metrics retrieved successfully.",
        data={
            "total_users": User.objects.filter(is_staff=False, is_superuser=False).count(),
            "active_users": User.objects.filter(is_active=True, is_staff=False, is_superuser=False).count(),
            "staff_users": User.objects.filter(is_staff=True).count(),
            "admins": User.objects.filter(is_superuser=True).count(),
        },
    )


@extend_schema(parameters=[OpenApiParameter("from", OpenApiTypes.DATE), OpenApiParameter("to", OpenApiTypes.DATE)], responses={200: OpenApiTypes.OBJECT, **DEFAULT_ERROR_RESPONSES})
@api_view(["GET"])
@permission_classes([IsAdminUser])
@handle_api_exceptions
def admin_nutrition_dashboard(request):
    logs = DailyLog.objects.all()
    date_from = request.query_params.get("from")
    date_to = request.query_params.get("to")
    if date_from:
        logs = logs.filter(date__gte=date_from)
    if date_to:
        logs = logs.filter(date__lte=date_to)
    return api_response(
        "Nutrition dashboard metrics retrieved successfully.",
        data={
            "log_count": logs.count(),
            "meal_count": MealEntry.objects.filter(log__in=logs).count(),
            "totals": log_totals(logs),
        },
    )


@extend_schema(responses={200: OpenApiTypes.OBJECT, **DEFAULT_ERROR_RESPONSES})
@api_view(["GET"])
@permission_classes([IsAdminUser])
@handle_api_exceptions
def admin_inference_dashboard(request):
    total = InferenceJob.objects.count()
    return api_response(
        "Inference dashboard metrics retrieved successfully.",
        data={
            "total_jobs": total,
            "jobs_by_status": dict(InferenceJob.objects.values_list("status").annotate(count=Count("id"))),
            "average_latency_ms": round(InferenceJob.objects.filter(latency_ms__gt=0).aggregate(value=Avg("latency_ms"))["value"] or 0, 2),
            "open_feedback": InferenceFeedback.objects.filter(status="open").count(),
        },
    )


@extend_schema(responses={200: OpenApiTypes.OBJECT, **DEFAULT_ERROR_RESPONSES})
@api_view(["GET"])
@permission_classes([IsAdminUser])
@handle_api_exceptions
def admin_system_usage_dashboard(request):
    return api_response(
        "System usage metrics retrieved successfully.",
        data={
            "meals_by_source": dict(MealEntry.objects.values_list("source_type").annotate(count=Count("id"))),
            "total_meals": MealEntry.objects.count(),
            "total_daily_logs": DailyLog.objects.count(),
            "total_inference_jobs": InferenceJob.objects.count(),
        },
    )
