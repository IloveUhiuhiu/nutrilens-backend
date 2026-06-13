from django.db.models import Avg, Count, Sum
from django.utils import timezone

from accounts.models import User
from analysis.models import DailyLog, MealEntry
from inference.models import InferenceFeedback, InferenceJob
from nutrients.models import HealthAdviceRule


def log_totals(queryset):
    """Chức năng: tính tổng dinh dưỡng logs. Đầu vào: queryset DailyLog. Đầu ra: dict tổng và trung bình."""
    totals = queryset.aggregate(
        sum_calories=Sum("total_calories"),
        total_protein=Sum("total_protein"),
        total_carbs=Sum("total_carbs"),
        total_fat=Sum("total_fat"),
        total_weight=Sum("total_weight"),
        average_calories=Avg("total_calories"),
    )
    return {key: round(value or 0, 2) for key, value in totals.items()}


def user_nutrition_summary(user, date_from, date_to):
    """Chức năng: tổng hợp dinh dưỡng user. Đầu vào: user và khoảng ngày. Đầu ra: dict summary."""
    logs = DailyLog.objects.filter(user=user, date__gte=date_from, date__lte=date_to)
    return {
        "from": date_from,
        "to": date_to,
        "tdee": user.tdee,
        "totals": log_totals(logs),
        "days": logs.count(),
    }


def user_nutrition_trends(user, date_from, date_to):
    """Chức năng: lấy xu hướng dinh dưỡng user. Đầu vào: user và khoảng ngày. Đầu ra: list theo ngày."""
    logs = DailyLog.objects.filter(user=user, date__gte=date_from, date__lte=date_to).order_by("date")
    return [
        {
            "date": log.date,
            "calories": log.total_calories,
            "protein": log.total_protein,
            "carbs": log.total_carbs,
            "fat": log.total_fat,
            "weight": log.total_weight,
            "tdee_percent": round((log.total_calories / user.tdee * 100), 2) if user.tdee else 0,
        }
        for log in logs
    ]


ADVICE_TITLES = {
    "normal": "Đang trong vùng an toàn",
    "warning": "Gần chạm giới hạn",
    "danger": "Đã vượt mục tiêu",
}


def user_nutrition_advice(user, date=None):
    """Chức năng: lấy tư vấn dinh dưỡng user. Đầu vào: user và ngày. Đầu ra: dict advice."""
    date = date or timezone.localdate()
    log = DailyLog.objects.filter(user=user, date=date).first()
    percent = round((log.total_calories / user.tdee * 100), 2) if log and user.tdee else 0
    rule = HealthAdviceRule.objects.filter(min_percent__lte=percent, max_percent__gte=percent).first()
    alert_level = rule.alert_level if rule else "normal"
    advice_content = rule.advice_content if rule else ""
    return {
        "date": date,
        "tdee_percent": percent,
        "ratio": round(percent / 100, 4),
        "alert_level": alert_level,
        "status": alert_level,
        "title": ADVICE_TITLES.get(alert_level, ADVICE_TITLES["normal"]),
        "message": advice_content,
        "advice_content": advice_content,
        "calories": round(log.total_calories, 2) if log else 0,
        "tdee": round(user.tdee, 2) if user.tdee else 0,
    }


def admin_user_metrics():
    """Chức năng: thống kê user cho admin. Đầu vào: không có. Đầu ra: dict metrics."""
    return {
        "total_users": User.objects.filter(is_staff=False, is_superuser=False).count(),
        "active_users": User.objects.filter(is_active=True, is_staff=False, is_superuser=False).count(),
        "staff_users": User.objects.filter(is_staff=True).count(),
        "admins": User.objects.filter(is_superuser=True).count(),
    }


def admin_nutrition_metrics(date_from=None, date_to=None):
    """Chức năng: thống kê dinh dưỡng admin. Đầu vào: khoảng ngày tùy chọn. Đầu ra: dict metrics."""
    logs = DailyLog.objects.all()
    if date_from:
        logs = logs.filter(date__gte=date_from)
    if date_to:
        logs = logs.filter(date__lte=date_to)
    return {
        "log_count": logs.count(),
        "meal_count": MealEntry.objects.filter(log__in=logs).count(),
        "totals": log_totals(logs),
    }


def admin_inference_metrics():
    """Chức năng: thống kê inference admin. Đầu vào: không có. Đầu ra: dict metrics."""
    return {
        "total_jobs": InferenceJob.objects.count(),
        "jobs_by_status": dict(InferenceJob.objects.values_list("status").annotate(count=Count("id"))),
        "average_latency_ms": round(InferenceJob.objects.filter(latency_ms__gt=0).aggregate(value=Avg("latency_ms"))["value"] or 0, 2),
        "open_feedback": InferenceFeedback.objects.filter(status="open").count(),
    }


def admin_system_usage_metrics():
    """Chức năng: thống kê sử dụng hệ thống. Đầu vào: không có. Đầu ra: dict metrics."""
    return {
        "meals_by_source": dict(MealEntry.objects.values_list("source_type").annotate(count=Count("id"))),
        "total_meals": MealEntry.objects.count(),
        "total_daily_logs": DailyLog.objects.count(),
        "total_inference_jobs": InferenceJob.objects.count(),
    }
