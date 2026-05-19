from django.db.models import Q
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, OpenApiTypes, extend_schema
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser, IsAuthenticated

from core.api import (
    API_EMPTY_RESPONSE,
    DEFAULT_ERROR_RESPONSES,
    api_response,
    handle_api_exceptions,
    not_found_response,
    paginate_queryset,
    validation_error_response,
)
from inference.models import InferenceJob
from nutrients.models import Food, PackagedFood
from nutrients.serializers import FoodSerializer
from .models import DailyLog, MealComponent, MealEntry
from .serializers import (
    DailyLogSerializer,
    ManualMealSerializer,
    MealBarcodeSerializer,
    MealEntrySerializer,
    MealFromInferenceSerializer,
    MealSearchSerializer,
    MealUpdateSerializer,
    get_or_create_daily_log,
    refresh_daily_log,
)


def user_meal_queryset(user):
    return MealEntry.objects.filter(log__user=user).select_related("log", "food", "packaged_food").prefetch_related("components")


def create_meal_from_totals(log, **kwargs):
    meal = MealEntry.objects.create(log=log, confirmed_at=timezone.now(), **kwargs)
    refresh_daily_log(log)
    return meal


@extend_schema(request=MealFromInferenceSerializer, responses={201: OpenApiTypes.OBJECT, **DEFAULT_ERROR_RESPONSES})
@api_view(["POST"])
@permission_classes([IsAuthenticated])
@handle_api_exceptions
def meal_from_inference(request):
    serializer = MealFromInferenceSerializer(data=request.data)
    if not serializer.is_valid():
        return validation_error_response(serializer)

    job = InferenceJob.objects.filter(id=serializer.validated_data["job_id"], user=request.user).first()
    if not job:
        return not_found_response("Inference job not found.", field="job_id")
    if job.status != "succeeded" or not hasattr(job, "result"):
        return api_response(
            "Inference result is not ready.",
            status_code=status.HTTP_400_BAD_REQUEST,
            errors={"job_id": ["Inference result is not ready."]},
        )

    log = get_or_create_daily_log(request.user, serializer.validated_data.get("date"))
    result = job.result
    meal = create_meal_from_totals(
        log,
        source_type="image",
        image_path=job.image,
        inference_job_id=job.id,
        notes=serializer.validated_data.get("notes", ""),
        total_calories=result.total_calories,
        total_protein=result.total_protein,
        total_carbs=result.total_carbs,
        total_fat=result.total_fat,
        total_weight=result.total_weight,
    )
    return api_response("Meal created from inference successfully.", status_code=status.HTTP_201_CREATED, data=MealEntrySerializer(meal).data)


@extend_schema(request=MealBarcodeSerializer, responses={201: OpenApiTypes.OBJECT, **DEFAULT_ERROR_RESPONSES})
@api_view(["POST"])
@permission_classes([IsAuthenticated])
@handle_api_exceptions
def meal_from_barcode(request):
    serializer = MealBarcodeSerializer(data=request.data)
    if not serializer.is_valid():
        return validation_error_response(serializer)

    packaged_food = PackagedFood.objects.filter(barcode=serializer.validated_data["barcode"], is_active=True).first()
    if not packaged_food:
        return not_found_response("Packaged food not found.", field="barcode")

    servings = serializer.validated_data["servings"]
    log = get_or_create_daily_log(request.user, serializer.validated_data.get("date"))
    meal = create_meal_from_totals(
        log,
        packaged_food=packaged_food,
        source_type="barcode",
        barcode=packaged_food.barcode,
        total_calories=packaged_food.cal_per_serving * servings,
        total_protein=packaged_food.protein_per_serving * servings,
        total_carbs=packaged_food.carb_per_serving * servings,
        total_fat=packaged_food.fat_per_serving * servings,
        total_weight=packaged_food.serving_size * servings,
    )
    return api_response("Meal created from barcode successfully.", status_code=status.HTTP_201_CREATED, data=MealEntrySerializer(meal).data)


@extend_schema(request=MealSearchSerializer, responses={200: OpenApiTypes.OBJECT, **DEFAULT_ERROR_RESPONSES})
@api_view(["POST"])
@permission_classes([IsAuthenticated])
@handle_api_exceptions
def meal_search(request):
    serializer = MealSearchSerializer(data=request.data)
    if not serializer.is_valid():
        return validation_error_response(serializer)

    query = serializer.validated_data["query"]
    foods = Food.objects.filter(Q(vi_name__icontains=query) | Q(en_name__icontains=query) | Q(category__icontains=query)).order_by("vi_name")[:20]
    return api_response(
        "Meal search completed successfully.",
        data={
            "query": query,
            "source_type": serializer.validated_data["source_type"],
            "results": FoodSerializer(foods, many=True).data,
        },
    )


@extend_schema(request=ManualMealSerializer, responses={201: OpenApiTypes.OBJECT, **DEFAULT_ERROR_RESPONSES})
@api_view(["POST"])
@permission_classes([IsAuthenticated])
@handle_api_exceptions
def meal_manual(request):
    serializer = ManualMealSerializer(data=request.data)
    if not serializer.is_valid():
        return validation_error_response(serializer)

    log = get_or_create_daily_log(request.user, serializer.validated_data.get("date"))
    meal = MealEntry.objects.create(
        log=log,
        food=serializer.validated_data.get("food"),
        source_type="manual",
        notes=serializer.validated_data.get("notes", ""),
        confirmed_at=timezone.now(),
        total_calories=serializer.validated_data.get("total_calories", 0),
        total_protein=serializer.validated_data.get("total_protein", 0),
        total_carbs=serializer.validated_data.get("total_carbs", 0),
        total_fat=serializer.validated_data.get("total_fat", 0),
        total_weight=serializer.validated_data.get("total_weight", 0),
    )

    for component in serializer.validated_data.get("components", []):
        MealComponent.objects.create(meal_entry=meal, **component)

    if meal.components.exists():
        meal.total_calories = sum(component.calories for component in meal.components.all())
        meal.total_protein = sum(component.protein for component in meal.components.all())
        meal.total_carbs = sum(component.carbs for component in meal.components.all())
        meal.total_fat = sum(component.fat for component in meal.components.all())
        meal.total_weight = sum(component.calculated_weight for component in meal.components.all())
        meal.save(update_fields=["total_calories", "total_protein", "total_carbs", "total_fat", "total_weight"])

    refresh_daily_log(log)
    return api_response("Manual meal created successfully.", status_code=status.HTTP_201_CREATED, data=MealEntrySerializer(meal).data)


@extend_schema(parameters=[OpenApiParameter("date", OpenApiTypes.DATE), OpenApiParameter("from", OpenApiTypes.DATE), OpenApiParameter("to", OpenApiTypes.DATE), OpenApiParameter("page", OpenApiTypes.INT)], responses={200: OpenApiTypes.OBJECT, **DEFAULT_ERROR_RESPONSES})
@api_view(["GET"])
@permission_classes([IsAuthenticated])
@handle_api_exceptions
def meal_list(request):
    queryset = user_meal_queryset(request.user).order_by("-meal_time")
    date = request.query_params.get("date")
    date_from = request.query_params.get("from")
    date_to = request.query_params.get("to")
    if date:
        queryset = queryset.filter(log__date=date)
    if date_from:
        queryset = queryset.filter(log__date__gte=date_from)
    if date_to:
        queryset = queryset.filter(log__date__lte=date_to)
    return api_response("Meals retrieved successfully.", data=paginate_queryset(request, queryset, MealEntrySerializer))


@extend_schema(request=MealUpdateSerializer, responses={200: OpenApiTypes.OBJECT, 204: API_EMPTY_RESPONSE, **DEFAULT_ERROR_RESPONSES})
@api_view(["GET", "PATCH", "DELETE"])
@permission_classes([IsAuthenticated])
@handle_api_exceptions
def meal_detail(request, id):
    meal = user_meal_queryset(request.user).filter(id=id).first()
    if not meal:
        return not_found_response("Meal not found.")
    if request.method == "GET":
        return api_response("Meal retrieved successfully.", data=MealEntrySerializer(meal).data)
    if request.method == "DELETE":
        log = meal.log
        meal.delete()
        refresh_daily_log(log)
        return api_response("Meal deleted successfully.")

    serializer = MealUpdateSerializer(data=request.data)
    if not serializer.is_valid():
        return validation_error_response(serializer)
    for field, value in serializer.validated_data.items():
        setattr(meal, field, value)
    meal.save()
    refresh_daily_log(meal.log)
    return api_response("Meal updated successfully.", data=MealEntrySerializer(meal).data)


@extend_schema(parameters=[OpenApiParameter("date", OpenApiTypes.DATE)], responses={200: OpenApiTypes.OBJECT, **DEFAULT_ERROR_RESPONSES})
@api_view(["GET"])
@permission_classes([IsAuthenticated])
@handle_api_exceptions
def daily_log(request):
    date = request.query_params.get("date") or timezone.localdate()
    log = DailyLog.objects.filter(user=request.user, date=date).first()
    if not log:
        return api_response("Daily log retrieved successfully.", data=None)
    return api_response("Daily log retrieved successfully.", data=DailyLogSerializer(log).data)


@extend_schema(parameters=[OpenApiParameter("from", OpenApiTypes.DATE, required=True), OpenApiParameter("to", OpenApiTypes.DATE, required=True)], responses={200: OpenApiTypes.OBJECT, **DEFAULT_ERROR_RESPONSES})
@api_view(["GET"])
@permission_classes([IsAuthenticated])
@handle_api_exceptions
def range_logs(request):
    date_from = request.query_params.get("from")
    date_to = request.query_params.get("to")
    if not date_from or not date_to:
        return api_response("Missing date range.", status_code=status.HTTP_400_BAD_REQUEST, errors={"date_range": ["Both from and to are required."]})
    logs = DailyLog.objects.filter(user=request.user, date__gte=date_from, date__lte=date_to).order_by("date")
    return api_response("Range logs retrieved successfully.", data=DailyLogSerializer(logs, many=True).data)


@extend_schema(responses={200: OpenApiTypes.OBJECT, **DEFAULT_ERROR_RESPONSES})
@api_view(["GET"])
@permission_classes([IsAdminUser])
@handle_api_exceptions
def admin_meal_list(request):
    queryset = MealEntry.objects.all().select_related("log", "log__user", "food", "packaged_food").order_by("-meal_time")
    user_id = request.query_params.get("user_id")
    if user_id:
        queryset = queryset.filter(log__user_id=user_id)
    return api_response("Meals retrieved successfully.", data=paginate_queryset(request, queryset, MealEntrySerializer))


@extend_schema(responses={200: OpenApiTypes.OBJECT, **DEFAULT_ERROR_RESPONSES})
@api_view(["GET"])
@permission_classes([IsAdminUser])
@handle_api_exceptions
def admin_meal_detail(request, id):
    meal = MealEntry.objects.filter(id=id).first()
    if not meal:
        return not_found_response("Meal not found.")
    return api_response("Meal retrieved successfully.", data=MealEntrySerializer(meal).data)


@extend_schema(responses={200: OpenApiTypes.OBJECT, **DEFAULT_ERROR_RESPONSES})
@api_view(["GET"])
@permission_classes([IsAdminUser])
@handle_api_exceptions
def admin_log_list(request):
    queryset = DailyLog.objects.all().select_related("user").order_by("-date")
    user_id = request.query_params.get("user_id")
    if user_id:
        queryset = queryset.filter(user_id=user_id)
    return api_response("Daily logs retrieved successfully.", data=paginate_queryset(request, queryset, DailyLogSerializer))


@extend_schema(responses={200: OpenApiTypes.OBJECT, **DEFAULT_ERROR_RESPONSES})
@api_view(["GET"])
@permission_classes([IsAdminUser])
@handle_api_exceptions
def admin_log_detail(request, id):
    log = DailyLog.objects.filter(id=id).first()
    if not log:
        return not_found_response("Daily log not found.")
    return api_response("Daily log retrieved successfully.", data=DailyLogSerializer(log).data)
