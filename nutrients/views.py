from django.db.models import Q
from drf_spectacular.utils import OpenApiParameter, OpenApiTypes, extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticated

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
    queryset = Food.objects.all().order_by("vi_name")
    search = request.query_params.get("search")
    category = request.query_params.get("category")
    if search:
        queryset = queryset.filter(Q(vi_name__icontains=search) | Q(en_name__icontains=search) | Q(fdc_id__icontains=search))
    if category:
        queryset = queryset.filter(category__iexact=category)
    return queryset


def filter_ingredients(request):
    queryset = IngredientPhysicalData.objects.all().order_by("vi_name")
    search = request.query_params.get("search")
    if search:
        queryset = queryset.filter(Q(vi_name__icontains=search) | Q(en_name__icontains=search) | Q(fdc_id_ref__icontains=search))
    return queryset


@extend_schema(
    parameters=[OpenApiParameter("search", OpenApiTypes.STR), OpenApiParameter("category", OpenApiTypes.STR), OpenApiParameter("page", OpenApiTypes.INT)],
    responses={200: OpenApiTypes.OBJECT, **DEFAULT_ERROR_RESPONSES},
)
@api_view(["GET"])
@permission_classes([AllowAny])
@handle_api_exceptions
def food_list(request):
    data = paginate_queryset(request, filter_foods(request), FoodSerializer)
    return api_response("Foods retrieved successfully.", data=data)


@extend_schema(responses={200: FOOD_RESPONSE, **DEFAULT_ERROR_RESPONSES})
@api_view(["GET"])
@permission_classes([AllowAny])
@handle_api_exceptions
def food_detail(request, id):
    food = Food.objects.filter(id=id).first()
    if not food:
        return not_found_response("Food not found.")
    return api_response("Food retrieved successfully.", data=FoodSerializer(food).data)


@extend_schema(
    parameters=[OpenApiParameter("search", OpenApiTypes.STR), OpenApiParameter("page", OpenApiTypes.INT)],
    responses={200: OpenApiTypes.OBJECT, **DEFAULT_ERROR_RESPONSES},
)
@api_view(["GET"])
@permission_classes([AllowAny])
@handle_api_exceptions
def ingredient_list(request):
    data = paginate_queryset(request, filter_ingredients(request), IngredientPhysicalDataSerializer)
    return api_response("Ingredients retrieved successfully.", data=data)


@extend_schema(responses={200: INGREDIENT_RESPONSE, **DEFAULT_ERROR_RESPONSES})
@api_view(["GET"])
@permission_classes([AllowAny])
@handle_api_exceptions
def ingredient_detail(request, id):
    ingredient = IngredientPhysicalData.objects.filter(id=id).first()
    if not ingredient:
        return not_found_response("Ingredient not found.")
    return api_response("Ingredient retrieved successfully.", data=IngredientPhysicalDataSerializer(ingredient).data)


@extend_schema(parameters=[OpenApiParameter("barcode", OpenApiTypes.STR)], responses={200: PACKAGED_FOOD_RESPONSE, **DEFAULT_ERROR_RESPONSES})
@api_view(["GET"])
@permission_classes([IsAuthenticated])
@handle_api_exceptions
def packaged_food_by_barcode(request, barcode):
    packaged_food = PackagedFood.objects.filter(barcode=barcode, is_active=True).first()
    if not packaged_food:
        return not_found_response("Packaged food not found.", field="barcode")
    return api_response("Packaged food retrieved successfully.", data=PackagedFoodSerializer(packaged_food).data)


def admin_list_create(request, queryset, serializer_class, success_name):
    if request.method == "GET":
        data = paginate_queryset(request, queryset, serializer_class)
        return api_response(f"{success_name} retrieved successfully.", data=data)
    serializer = serializer_class(data=request.data)
    if not serializer.is_valid():
        return validation_error_response(serializer)
    obj = serializer.save()
    return api_response(f"{success_name} created successfully.", status_code=status.HTTP_201_CREATED, data=serializer_class(obj).data)


def admin_detail_update_delete(request, obj, serializer_class, label):
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


@extend_schema(request=FoodSerializer, responses={200: OpenApiTypes.OBJECT, 201: FOOD_RESPONSE, **DEFAULT_ERROR_RESPONSES})
@api_view(["GET", "POST"])
@permission_classes([IsAdminUser])
@handle_api_exceptions
def admin_food_list_create(request):
    return admin_list_create(request, filter_foods(request), FoodSerializer, "Foods")


@extend_schema(request=FoodSerializer, responses={200: FOOD_RESPONSE, 204: API_EMPTY_RESPONSE, **DEFAULT_ERROR_RESPONSES})
@api_view(["GET", "PATCH", "DELETE"])
@permission_classes([IsAdminUser])
@handle_api_exceptions
def admin_food_detail(request, id):
    return admin_detail_update_delete(request, Food.objects.filter(id=id).first(), FoodSerializer, "Food")


@extend_schema(request=IngredientPhysicalDataSerializer, responses={200: OpenApiTypes.OBJECT, 201: INGREDIENT_RESPONSE, **DEFAULT_ERROR_RESPONSES})
@api_view(["GET", "POST"])
@permission_classes([IsAdminUser])
@handle_api_exceptions
def admin_ingredient_list_create(request):
    return admin_list_create(request, filter_ingredients(request), IngredientPhysicalDataSerializer, "Ingredients")


@extend_schema(request=IngredientPhysicalDataSerializer, responses={200: INGREDIENT_RESPONSE, 204: API_EMPTY_RESPONSE, **DEFAULT_ERROR_RESPONSES})
@api_view(["GET", "PATCH", "DELETE"])
@permission_classes([IsAdminUser])
@handle_api_exceptions
def admin_ingredient_detail(request, id):
    return admin_detail_update_delete(request, IngredientPhysicalData.objects.filter(id=id).first(), IngredientPhysicalDataSerializer, "Ingredient")


@extend_schema(request=HealthAdviceRuleSerializer, responses={200: OpenApiTypes.OBJECT, **DEFAULT_ERROR_RESPONSES})
@api_view(["GET", "POST"])
@permission_classes([IsAdminUser])
@handle_api_exceptions
def admin_advice_rule_list_create(request):
    return admin_list_create(request, HealthAdviceRule.objects.all().order_by("min_percent"), HealthAdviceRuleSerializer, "Advice rules")


@extend_schema(request=HealthAdviceRuleSerializer, responses={200: OpenApiTypes.OBJECT, **DEFAULT_ERROR_RESPONSES})
@api_view(["GET", "PATCH", "DELETE"])
@permission_classes([IsAdminUser])
@handle_api_exceptions
def admin_advice_rule_detail(request, id):
    return admin_detail_update_delete(request, HealthAdviceRule.objects.filter(id=id).first(), HealthAdviceRuleSerializer, "Advice rule")


@extend_schema(request=PackagedFoodSerializer, responses={200: OpenApiTypes.OBJECT, 201: PACKAGED_FOOD_RESPONSE, **DEFAULT_ERROR_RESPONSES})
@api_view(["GET", "POST"])
@permission_classes([IsAdminUser])
@handle_api_exceptions
def admin_packaged_food_list_create(request):
    queryset = PackagedFood.objects.all().order_by("name")
    search = request.query_params.get("search")
    if search:
        queryset = queryset.filter(Q(barcode__icontains=search) | Q(name__icontains=search) | Q(brand__icontains=search))
    return admin_list_create(request, queryset, PackagedFoodSerializer, "Packaged foods")


@extend_schema(request=PackagedFoodSerializer, responses={200: PACKAGED_FOOD_RESPONSE, **DEFAULT_ERROR_RESPONSES})
@api_view(["GET", "PATCH", "DELETE"])
@permission_classes([IsAdminUser])
@handle_api_exceptions
def admin_packaged_food_detail(request, id):
    return admin_detail_update_delete(request, PackagedFood.objects.filter(id=id).first(), PackagedFoodSerializer, "Packaged food")
