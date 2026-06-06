from django.db.models import Q
from django.conf import settings
from drf_spectacular.utils import OpenApiParameter, OpenApiTypes, extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAdminUser

from core.api import (
    API_EMPTY_RESPONSE,
    DEFAULT_ERROR_RESPONSES,
    api_response,
    handle_api_exceptions,
    not_found_response,
    paginate_queryset,
    validation_error_response,
)
from .models import Food, HealthAdviceRule, IngredientPhysicalData, PackagedFood
from .serializers import (
    FoodSerializer,
    HealthAdviceRuleSerializer,
    IngredientPhysicalDataSerializer,
    PackagedFoodSerializer,
)


FOOD_RESPONSE = inline_serializer(
    name="FoodApiResponse",
    fields={"status_code": serializers.IntegerField(), "message": serializers.CharField(), "data": FoodSerializer(), "errors": serializers.JSONField(allow_null=True)},
)
INGREDIENT_RESPONSE = inline_serializer(
    name="IngredientApiResponse",
    fields={"status_code": serializers.IntegerField(), "message": serializers.CharField(), "data": IngredientPhysicalDataSerializer(), "errors": serializers.JSONField(allow_null=True)},
)
PACKAGED_FOOD_RESPONSE = inline_serializer(
    name="PackagedFoodApiResponse",
    fields={"status_code": serializers.IntegerField(), "message": serializers.CharField(), "data": PackagedFoodSerializer(), "errors": serializers.JSONField(allow_null=True)},
)


def filter_foods(request):
    """Chức năng: lọc danh sách món ăn. Đầu vào: query params search/category. Đầu ra: queryset Food."""
    queryset = Food.objects.all().order_by("vi_name")
    search = request.query_params.get("search")
    category = request.query_params.get("category")
    if search:
        queryset = queryset.filter(Q(vi_name__icontains=search) | Q(en_name__icontains=search) | Q(fdc_id__icontains=search))
    if category:
        queryset = queryset.filter(category__iexact=category)
    return queryset


def filter_ingredients(request):
    """Chức năng: lọc danh sách nguyên liệu. Đầu vào: query param search. Đầu ra: queryset IngredientPhysicalData."""
    queryset = IngredientPhysicalData.objects.all().order_by("vi_name")
    search = request.query_params.get("search")
    if search:
        queryset = queryset.filter(Q(vi_name__icontains=search) | Q(en_name__icontains=search) | Q(fdc_id_ref__icontains=search))
    return queryset


@extend_schema(
    summary="Danh sách món ăn",
    parameters=[OpenApiParameter("search", OpenApiTypes.STR), OpenApiParameter("category", OpenApiTypes.STR), OpenApiParameter("page", OpenApiTypes.INT)],
    responses={200: OpenApiTypes.OBJECT, **DEFAULT_ERROR_RESPONSES},
)
@api_view(["GET"])
@permission_classes([AllowAny])
@handle_api_exceptions
def food_list(request):
    """Chức năng: API danh sách món ăn. Đầu vào: search/category/page. Đầu ra: danh sách Food phân trang."""
    data = paginate_queryset(request, filter_foods(request), FoodSerializer)
    return api_response("Foods retrieved successfully.", data=data)


@extend_schema(summary="Chi tiết món ăn", responses={200: FOOD_RESPONSE, **DEFAULT_ERROR_RESPONSES})
@api_view(["GET"])
@permission_classes([AllowAny])
@handle_api_exceptions
def food_detail(request, id):
    """Chức năng: API chi tiết món ăn. Đầu vào: food id. Đầu ra: thông tin Food hoặc lỗi 404."""
    food = Food.objects.filter(id=id).first()
    if not food:
        return not_found_response("Food not found.")
    return api_response("Food retrieved successfully.", data=FoodSerializer(food).data)


@extend_schema(
    summary="Danh sách nguyên liệu",
    parameters=[OpenApiParameter("search", OpenApiTypes.STR), OpenApiParameter("page", OpenApiTypes.INT)],
    responses={200: OpenApiTypes.OBJECT, **DEFAULT_ERROR_RESPONSES},
)
@api_view(["GET"])
@permission_classes([AllowAny])
@handle_api_exceptions
def ingredient_list(request):
    """Chức năng: API danh sách nguyên liệu. Đầu vào: search/page. Đầu ra: danh sách Ingredient phân trang."""
    data = paginate_queryset(request, filter_ingredients(request), IngredientPhysicalDataSerializer)
    return api_response("Ingredients retrieved successfully.", data=data)


@extend_schema(summary="Chi tiết nguyên liệu", responses={200: INGREDIENT_RESPONSE, **DEFAULT_ERROR_RESPONSES})
@api_view(["GET"])
@permission_classes([AllowAny])
@handle_api_exceptions
def ingredient_detail(request, id):
    """Chức năng: API chi tiết nguyên liệu. Đầu vào: ingredient id. Đầu ra: thông tin Ingredient hoặc lỗi 404."""
    ingredient = IngredientPhysicalData.objects.filter(id=id).first()
    if not ingredient:
        return not_found_response("Ingredient not found.")
    return api_response("Ingredient retrieved successfully.", data=IngredientPhysicalDataSerializer(ingredient).data)


@extend_schema(summary="Internal danh sách dữ liệu nguyên liệu cho AI", responses={200: OpenApiTypes.OBJECT, **DEFAULT_ERROR_RESPONSES})
@api_view(["GET"])
@permission_classes([AllowAny])
@handle_api_exceptions
def internal_ingredient_physical_data(request):
    """Chức năng: API nội bộ trả dữ liệu nguyên liệu cho AI server. Đầu vào: X-Internal-API-Key. Đầu ra: list Ingredient."""
    api_key = request.headers.get("X-Internal-API-Key", "")
    if not settings.INTERNAL_API_KEY or api_key != settings.INTERNAL_API_KEY:
        return api_response(
            "Invalid internal API key.",
            status_code=403,
            errors={"authorization": ["Invalid internal API key."]},
        )
    queryset = IngredientPhysicalData.objects.all().order_by("en_name")
    return api_response(
        "Ingredient physical data retrieved successfully.",
        data=IngredientPhysicalDataSerializer(queryset, many=True).data,
    )


def admin_list_create(request, queryset, serializer_class, success_name):
    """Chức năng: helper list/create admin. Đầu vào: request, queryset, serializer. Đầu ra: response list hoặc object mới."""
    if request.method == "GET":
        data = paginate_queryset(request, queryset, serializer_class)
        return api_response(f"{success_name} retrieved successfully.", data=data)
    serializer = serializer_class(data=request.data)
    if not serializer.is_valid():
        return validation_error_response(serializer)
    obj = serializer.save()
    return api_response(f"{success_name} created successfully.", status_code=status.HTTP_201_CREATED, data=serializer_class(obj).data)


def admin_detail_update_delete(request, obj, serializer_class, label):
    """Chức năng: helper detail/update/delete admin. Đầu vào: request, object, serializer. Đầu ra: response tương ứng."""
    if not obj:
        return not_found_response(f"{label} not found.")
    if request.method == "GET":
        return api_response(f"{label} retrieved successfully.", data=serializer_class(obj).data)
    if request.method == "DELETE":
        obj.delete()
        return api_response(f"{label} deleted successfully.", data=None)
    serializer = serializer_class(obj, data=request.data, partial=True)
    if not serializer.is_valid():
        return validation_error_response(serializer)
    serializer.save()
    return api_response(f"{label} updated successfully.", data=serializer.data)


@extend_schema(summary="Admin danh sách và tạo món ăn", request=FoodSerializer, responses={200: OpenApiTypes.OBJECT, 201: FOOD_RESPONSE, **DEFAULT_ERROR_RESPONSES})
@api_view(["GET", "POST"])
@permission_classes([IsAdminUser])
@handle_api_exceptions
def admin_food_list_create(request):
    """Chức năng: API admin list/create món ăn. Đầu vào: filter hoặc payload Food. Đầu ra: danh sách hoặc Food mới."""
    return admin_list_create(request, filter_foods(request), FoodSerializer, "Foods")


@extend_schema(summary="Admin chi tiết món ăn", request=FoodSerializer, responses={200: FOOD_RESPONSE, 204: API_EMPTY_RESPONSE, **DEFAULT_ERROR_RESPONSES})
@api_view(["GET", "PATCH", "DELETE"])
@permission_classes([IsAdminUser])
@handle_api_exceptions
def admin_food_detail(request, id):
    """Chức năng: API admin xem/sửa/xóa món ăn. Đầu vào: food id và payload tùy method. Đầu ra: Food hoặc xác nhận xóa."""
    return admin_detail_update_delete(request, Food.objects.filter(id=id).first(), FoodSerializer, "Food")


@extend_schema(summary="Admin danh sách và tạo nguyên liệu", request=IngredientPhysicalDataSerializer, responses={200: OpenApiTypes.OBJECT, 201: INGREDIENT_RESPONSE, **DEFAULT_ERROR_RESPONSES})
@api_view(["GET", "POST"])
@permission_classes([IsAdminUser])
@handle_api_exceptions
def admin_ingredient_list_create(request):
    """Chức năng: API admin list/create nguyên liệu. Đầu vào: filter hoặc payload Ingredient. Đầu ra: danh sách hoặc Ingredient mới."""
    return admin_list_create(request, filter_ingredients(request), IngredientPhysicalDataSerializer, "Ingredients")


@extend_schema(summary="Admin chi tiết nguyên liệu", request=IngredientPhysicalDataSerializer, responses={200: INGREDIENT_RESPONSE, 204: API_EMPTY_RESPONSE, **DEFAULT_ERROR_RESPONSES})
@api_view(["GET", "PATCH", "DELETE"])
@permission_classes([IsAdminUser])
@handle_api_exceptions
def admin_ingredient_detail(request, id):
    """Chức năng: API admin xem/sửa/xóa nguyên liệu. Đầu vào: ingredient id và payload tùy method. Đầu ra: Ingredient hoặc xác nhận xóa."""
    return admin_detail_update_delete(request, IngredientPhysicalData.objects.filter(id=id).first(), IngredientPhysicalDataSerializer, "Ingredient")


@extend_schema(summary="Admin danh sách và tạo rule tư vấn", request=HealthAdviceRuleSerializer, responses={200: OpenApiTypes.OBJECT, **DEFAULT_ERROR_RESPONSES})
@api_view(["GET", "POST"])
@permission_classes([IsAdminUser])
@handle_api_exceptions
def admin_advice_rule_list_create(request):
    """Chức năng: API admin list/create rule tư vấn. Đầu vào: payload rule nếu POST. Đầu ra: danh sách hoặc rule mới."""
    return admin_list_create(request, HealthAdviceRule.objects.all().order_by("min_percent"), HealthAdviceRuleSerializer, "Advice rules")


@extend_schema(summary="Admin chi tiết rule tư vấn", request=HealthAdviceRuleSerializer, responses={200: OpenApiTypes.OBJECT, **DEFAULT_ERROR_RESPONSES})
@api_view(["GET", "PATCH", "DELETE"])
@permission_classes([IsAdminUser])
@handle_api_exceptions
def admin_advice_rule_detail(request, id):
    """Chức năng: API admin xem/sửa/xóa rule tư vấn. Đầu vào: rule id và payload tùy method. Đầu ra: rule hoặc xác nhận xóa."""
    return admin_detail_update_delete(request, HealthAdviceRule.objects.filter(id=id).first(), HealthAdviceRuleSerializer, "Advice rule")


@extend_schema(summary="Admin danh sách và tạo packaged food", request=PackagedFoodSerializer, responses={200: OpenApiTypes.OBJECT, 201: PACKAGED_FOOD_RESPONSE, **DEFAULT_ERROR_RESPONSES})
@api_view(["GET", "POST"])
@permission_classes([IsAdminUser])
@handle_api_exceptions
def admin_packaged_food_list_create(request):
    """Chức năng: API admin list/create packaged food. Đầu vào: search hoặc payload. Đầu ra: danh sách hoặc PackagedFood mới."""
    queryset = PackagedFood.objects.all().order_by("name")
    search = request.query_params.get("search")
    if search:
        queryset = queryset.filter(Q(barcode__icontains=search) | Q(name__icontains=search) | Q(brand__icontains=search))
    return admin_list_create(request, queryset, PackagedFoodSerializer, "Packaged foods")


@extend_schema(summary="Admin chi tiết packaged food", request=PackagedFoodSerializer, responses={200: PACKAGED_FOOD_RESPONSE, **DEFAULT_ERROR_RESPONSES})
@api_view(["GET", "PATCH", "DELETE"])
@permission_classes([IsAdminUser])
@handle_api_exceptions
def admin_packaged_food_detail(request, id):
    """Chức năng: API admin xem/sửa/xóa packaged food. Đầu vào: packaged food id và payload tùy method. Đầu ra: object hoặc xác nhận xóa."""
    return admin_detail_update_delete(request, PackagedFood.objects.filter(id=id).first(), PackagedFoodSerializer, "Packaged food")
