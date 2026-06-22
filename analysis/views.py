from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, OpenApiTypes, extend_schema
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes

from core.permissions import method_perm, require_perm

from core.api import (
    API_EMPTY_RESPONSE,
    DEFAULT_ERROR_RESPONSES,
    api_response,
    external_service_error_response,
    handle_api_exceptions,
    not_found_response,
    paginate_queryset,
    validation_error_response,
)
from nutrients.clients import ExternalLookupError
from nutrients.services import get_or_lookup_barcode, search_usda_top_foods
from nutrients.serializers import PackagedFoodSerializer
from .models import DailyLog, MealEntry
from .serializers import (
    AdminDailyLogSerializer,
    AdminMealEntryListSerializer,
    DailyLogSerializer,
    ManualMealSerializer,
    MealBarcodeSerializer,
    MealEntrySerializer,
    MealFromInferenceSerializer,
    MealFromUSDASerializer,
    MealSearchSerializer,
    MealUpdateSerializer,
    refresh_daily_log,
)
from .services import (
    AnalysisServiceError,
    create_manual_meal,
    create_meal_from_barcode as create_barcode_meal,
    create_meal_from_inference as create_inference_meal,
    create_meal_from_usda as create_usda_meal,
    recalculate_meal_quantity,
)


def user_meal_queryset(user):
    """Chức năng: lấy meal của user. Đầu vào: user. Đầu ra: queryset MealEntry đã tối ưu quan hệ."""
    return MealEntry.objects.filter(log__user=user).select_related("log", "food", "packaged_food").prefetch_related("components")


@extend_schema(summary="Tra cứu barcode", parameters=[OpenApiParameter("barcode", OpenApiTypes.STR)], responses={200: OpenApiTypes.OBJECT, **DEFAULT_ERROR_RESPONSES})
@api_view(["GET"])
@permission_classes([require_perm("nutrients.view_packagedfood")])
@handle_api_exceptions
def barcode_lookup(request, barcode):
    """Chức năng: API tra barcode local trước, thiếu thì gọi OFF. Đầu vào: barcode. Đầu ra: PackagedFood hoặc lỗi."""
    try:
        packaged_food = get_or_lookup_barcode(barcode)
    except ExternalLookupError as exc:
        return external_service_error_response(exc, service_name="open_food_facts")
    if not packaged_food:
        return not_found_response("Packaged food not found.", field="barcode")
    return api_response("Packaged food retrieved successfully.", data=PackagedFoodSerializer(packaged_food).data)


@extend_schema(summary="Tạo bữa ăn từ kết quả AI", request=MealFromInferenceSerializer, responses={201: OpenApiTypes.OBJECT, **DEFAULT_ERROR_RESPONSES})
@api_view(["POST"])
@permission_classes([require_perm("analysis.add_mealentry")])
@handle_api_exceptions
def meal_from_inference(request):
    """Chức năng: API tạo meal từ kết quả AI. Đầu vào: job_id, date, notes. Đầu ra: MealEntry hoặc lỗi."""
    serializer = MealFromInferenceSerializer(data=request.data)
    if not serializer.is_valid():
        return validation_error_response(serializer)

    _override_keys = ("total_calories", "total_protein", "total_carbs", "total_fat", "total_weight")
    nutrition_overrides = {k: serializer.validated_data[k] for k in _override_keys if k in serializer.validated_data}
    try:
        meal = create_inference_meal(
            request.user,
            serializer.validated_data["job_id"],
            date=serializer.validated_data.get("date"),
            notes=serializer.validated_data.get("notes", ""),
            nutrition_overrides=nutrition_overrides or None,
        )
    except AnalysisServiceError as exc:
        status_code = status.HTTP_404_NOT_FOUND if exc.field == "job_id" and "not found" in exc.message.lower() else status.HTTP_400_BAD_REQUEST
        return api_response(
            exc.message,
            status_code=status_code,
            errors={exc.field: [exc.message]},
        )
    return api_response("Meal created from inference successfully.", status_code=status.HTTP_201_CREATED, data=MealEntrySerializer(meal).data)


@extend_schema(summary="Tạo bữa ăn từ barcode", request=MealBarcodeSerializer, responses={201: OpenApiTypes.OBJECT, **DEFAULT_ERROR_RESPONSES})
@api_view(["POST"])
@permission_classes([require_perm("analysis.add_mealentry")])
@handle_api_exceptions
def meal_from_barcode(request):
    """Chức năng: API tạo meal từ barcode đã tra cứu/local. Đầu vào: barcode, servings, date. Đầu ra: MealEntry."""
    serializer = MealBarcodeSerializer(data=request.data)
    if not serializer.is_valid():
        return validation_error_response(serializer)

    try:
        meal = create_barcode_meal(
            request.user,
            serializer.validated_data["barcode"],
            servings=serializer.validated_data["servings"],
            date=serializer.validated_data.get("date"),
        )
    except ExternalLookupError as exc:
        return external_service_error_response(exc, service_name="open_food_facts")
    except AnalysisServiceError as exc:
        return api_response(exc.message, status_code=status.HTTP_404_NOT_FOUND, errors={exc.field: [exc.message]})
    return api_response("Meal created from barcode successfully.", status_code=status.HTTP_201_CREATED, data=MealEntrySerializer(meal).data)


@extend_schema(summary="Tìm kiếm top 5 món ăn bằng USDA", request=MealSearchSerializer, responses={200: OpenApiTypes.OBJECT, **DEFAULT_ERROR_RESPONSES})
@api_view(["POST"])
@permission_classes([require_perm("nutrients.view_food")])
@handle_api_exceptions
def meal_search(request):
    """Chức năng: API tìm top 5 món USDA. Đầu vào: query/source_type. Đầu ra: kết quả dùng đơn vị gram."""
    serializer = MealSearchSerializer(data=request.data)
    if not serializer.is_valid():
        return validation_error_response(serializer)

    query = serializer.validated_data["query"]
    try:
        data = search_usda_top_foods(
            query,
            limit=serializer.validated_data["page_size"],
        )
    except ExternalLookupError as exc:
        return external_service_error_response(exc, service_name="usda")

    data["source_type"] = serializer.validated_data["source_type"]
    return api_response(
        "Meal search completed successfully.",
        data=data,
    )


@extend_schema(summary="Tạo bữa ăn từ USDA", request=MealFromUSDASerializer, responses={201: OpenApiTypes.OBJECT, **DEFAULT_ERROR_RESPONSES})
@api_view(["POST"])
@permission_classes([require_perm("analysis.add_mealentry")])
@handle_api_exceptions
def meal_from_usda(request):
    """Chức năng: API tạo meal từ Food USDA. Đầu vào: fdc_id và grams. Đầu ra: MealEntry."""
    serializer = MealFromUSDASerializer(data=request.data)
    if not serializer.is_valid():
        return validation_error_response(serializer)

    try:
        meal = create_usda_meal(
            request.user,
            serializer.validated_data["fdc_id"],
            serializer.validated_data["grams"],
            date=serializer.validated_data.get("date"),
            source_type=serializer.validated_data["source_type"],
            search_query=serializer.validated_data.get("search_query", ""),
        )
    except ExternalLookupError as exc:
        return external_service_error_response(exc, service_name="usda")
    return api_response("Meal created from USDA successfully.", status_code=status.HTTP_201_CREATED, data=MealEntrySerializer(meal).data)


@extend_schema(summary="Tạo bữa ăn thủ công", request=ManualMealSerializer, responses={201: OpenApiTypes.OBJECT, **DEFAULT_ERROR_RESPONSES})
@api_view(["POST"])
@permission_classes([require_perm("analysis.add_mealentry")])
@handle_api_exceptions
def meal_manual(request):
    """Chức năng: API tạo meal thủ công. Đầu vào: food, components hoặc tổng dinh dưỡng. Đầu ra: MealEntry."""
    serializer = ManualMealSerializer(data=request.data)
    if not serializer.is_valid():
        return validation_error_response(serializer)

    meal = create_manual_meal(request.user, serializer.validated_data)
    return api_response("Manual meal created successfully.", status_code=status.HTTP_201_CREATED, data=MealEntrySerializer(meal).data)


@extend_schema(summary="Danh sách bữa ăn", parameters=[OpenApiParameter("date", OpenApiTypes.DATE), OpenApiParameter("from", OpenApiTypes.DATE), OpenApiParameter("to", OpenApiTypes.DATE), OpenApiParameter("page", OpenApiTypes.INT)], responses={200: OpenApiTypes.OBJECT, **DEFAULT_ERROR_RESPONSES})
@api_view(["GET"])
@permission_classes([require_perm("analysis.view_mealentry")])
@handle_api_exceptions
def meal_list(request):
    """Chức năng: API danh sách meal của user. Đầu vào: date/from/to/page. Đầu ra: danh sách MealEntry phân trang."""
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


@extend_schema(summary="Chi tiết bữa ăn", request=MealUpdateSerializer, responses={200: OpenApiTypes.OBJECT, 204: API_EMPTY_RESPONSE, **DEFAULT_ERROR_RESPONSES})
@api_view(["GET", "PATCH", "DELETE"])
@permission_classes([method_perm(
    GET="analysis.view_mealentry",
    PATCH="analysis.change_mealentry",
    DELETE="analysis.delete_mealentry",
)])
@handle_api_exceptions
def meal_detail(request, id):
    """Chức năng: API xem/sửa/xóa meal. Đầu vào: meal id và payload tùy method. Đầu ra: MealEntry hoặc xác nhận xóa."""
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
    validated_data = dict(serializer.validated_data)
    serving_amount = validated_data.pop("serving_amount", None)
    if serving_amount is not None:
        recalculate_meal_quantity(meal, serving_amount)
    for field, value in validated_data.items():
        setattr(meal, field, value)
    meal.save()
    refresh_daily_log(meal.log)
    return api_response("Meal updated successfully.", data=MealEntrySerializer(meal).data)


@extend_schema(summary="Nhật ký dinh dưỡng theo ngày", parameters=[OpenApiParameter("date", OpenApiTypes.DATE)], responses={200: OpenApiTypes.OBJECT, **DEFAULT_ERROR_RESPONSES})
@api_view(["GET"])
@permission_classes([require_perm("analysis.view_dailylog")])
@handle_api_exceptions
def daily_log(request):
    """Chức năng: API nhật ký ngày. Đầu vào: date tùy chọn. Đầu ra: DailyLog của user hoặc null."""
    date = request.query_params.get("date") or timezone.localdate()
    log = DailyLog.objects.filter(user=request.user, date=date).first()
    if not log:
        return api_response("Daily log retrieved successfully.", data=None)
    return api_response("Daily log retrieved successfully.", data=DailyLogSerializer(log).data)


@extend_schema(summary="Nhật ký dinh dưỡng theo khoảng ngày", parameters=[OpenApiParameter("from", OpenApiTypes.DATE, required=True), OpenApiParameter("to", OpenApiTypes.DATE, required=True)], responses={200: OpenApiTypes.OBJECT, **DEFAULT_ERROR_RESPONSES})
@api_view(["GET"])
@permission_classes([require_perm("analysis.view_dailylog")])
@handle_api_exceptions
def range_logs(request):
    """Chức năng: API nhật ký theo khoảng ngày. Đầu vào: from và to. Đầu ra: danh sách DailyLog."""
    date_from = request.query_params.get("from")
    date_to = request.query_params.get("to")
    if not date_from or not date_to:
        return api_response("Missing date range.", status_code=status.HTTP_400_BAD_REQUEST, errors={"date_range": ["Both from and to are required."]})
    logs = DailyLog.objects.filter(user=request.user, date__gte=date_from, date__lte=date_to).order_by("date")
    return api_response("Range logs retrieved successfully.", data=DailyLogSerializer(logs, many=True).data)


@extend_schema(
    summary="Admin danh sách bữa ăn",
    parameters=[
        OpenApiParameter("search", OpenApiTypes.STR),
        OpenApiParameter("user_id", OpenApiTypes.STR),
        OpenApiParameter("source_type", OpenApiTypes.STR),
        OpenApiParameter("start_date", OpenApiTypes.DATE),
        OpenApiParameter("end_date", OpenApiTypes.DATE),
        OpenApiParameter("page", OpenApiTypes.INT),
    ],
    responses={200: OpenApiTypes.OBJECT, **DEFAULT_ERROR_RESPONSES},
)
@api_view(["GET"])
@permission_classes([require_perm("analysis.view_mealentry")])
@handle_api_exceptions
def admin_meal_list(request):
    """Chức năng: API admin danh sách meal. Đầu vào: search/user_id/source_type/date/page. Đầu ra: danh sách MealEntry phân trang."""
    from django.db.models import Q
    queryset = MealEntry.objects.all().select_related("log", "log__user", "food", "packaged_food").order_by("-meal_time")
    user_id = request.query_params.get("user_id")
    search = request.query_params.get("search")
    source_type = request.query_params.get("source_type")
    start_date = request.query_params.get("start_date")
    end_date = request.query_params.get("end_date")

    if user_id:
        queryset = queryset.filter(log__user_id=user_id)
    if search:
        queryset = queryset.filter(
            Q(id__icontains=search)
            | Q(log__user__email__icontains=search)
            | Q(barcode__icontains=search)
            | Q(search_query__icontains=search)
        )
    if source_type:
        queryset = queryset.filter(source_type=source_type)
    if start_date:
        queryset = queryset.filter(log__date__gte=start_date)
    if end_date:
        queryset = queryset.filter(log__date__lte=end_date)

    return api_response("Meals retrieved successfully.", data=paginate_queryset(request, queryset, AdminMealEntryListSerializer))


@extend_schema(summary="Admin chi tiết bữa ăn", responses={200: OpenApiTypes.OBJECT, **DEFAULT_ERROR_RESPONSES})
@api_view(["GET"])
@permission_classes([require_perm("analysis.view_mealentry")])
@handle_api_exceptions
def admin_meal_detail(request, id):
    """Chức năng: API admin chi tiết meal. Đầu vào: meal id. Đầu ra: MealEntry hoặc lỗi 404."""
    meal = MealEntry.objects.filter(id=id).first()
    if not meal:
        return not_found_response("Meal not found.")
    return api_response("Meal retrieved successfully.", data=MealEntrySerializer(meal).data)


@extend_schema(
    summary="Admin danh sách nhật ký",
    parameters=[
        OpenApiParameter("search", OpenApiTypes.STR),
        OpenApiParameter("user_id", OpenApiTypes.STR),
        OpenApiParameter("start_date", OpenApiTypes.DATE),
        OpenApiParameter("end_date", OpenApiTypes.DATE),
        OpenApiParameter("page", OpenApiTypes.INT),
    ],
    responses={200: OpenApiTypes.OBJECT, **DEFAULT_ERROR_RESPONSES},
)
@api_view(["GET"])
@permission_classes([require_perm("analysis.view_dailylog")])
@handle_api_exceptions
def admin_log_list(request):
    """Chức năng: API admin danh sách log. Đầu vào: search/user_id/date/page. Đầu ra: danh sách DailyLog phân trang."""
    from django.db.models import Q
    queryset = DailyLog.objects.all().select_related("user").prefetch_related("meals").order_by("-date")
    user_id = request.query_params.get("user_id")
    search = request.query_params.get("search")
    start_date = request.query_params.get("start_date")
    end_date = request.query_params.get("end_date")

    if user_id:
        queryset = queryset.filter(user_id=user_id)
    if search:
        queryset = queryset.filter(
            Q(id__icontains=search) | Q(user__email__icontains=search)
        )
    if start_date:
        queryset = queryset.filter(date__gte=start_date)
    if end_date:
        queryset = queryset.filter(date__lte=end_date)

    return api_response("Daily logs retrieved successfully.", data=paginate_queryset(request, queryset, AdminDailyLogSerializer))


@extend_schema(summary="Admin chi tiết nhật ký", responses={200: OpenApiTypes.OBJECT, **DEFAULT_ERROR_RESPONSES})
@api_view(["GET"])
@permission_classes([require_perm("analysis.view_dailylog")])
@handle_api_exceptions
def admin_log_detail(request, id):
    """Chức năng: API admin chi tiết log. Đầu vào: log id. Đầu ra: DailyLog hoặc lỗi 404."""
    log = DailyLog.objects.filter(id=id).first()
    if not log:
        return not_found_response("Daily log not found.")
    return api_response("Daily log retrieved successfully.", data=DailyLogSerializer(log).data)
