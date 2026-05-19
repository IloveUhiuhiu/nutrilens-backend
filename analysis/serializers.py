from django.utils import timezone
from rest_framework import serializers

from nutrients.models import Food, IngredientPhysicalData, PackagedFood
from nutrients.serializers import FoodSerializer, PackagedFoodSerializer
from .models import DailyLog, MealComponent, MealEntry


class MealComponentSerializer(serializers.ModelSerializer):
    physical_data_name = serializers.CharField(source="physical_data.vi_name", read_only=True)

    class Meta:
        model = MealComponent
        fields = (
            "id",
            "physical_data",
            "physical_data_name",
            "component_name",
            "mask_path",
            "volume",
            "calculated_weight",
            "calories",
            "protein",
            "carbs",
            "fat",
        )
        read_only_fields = ("id", "calculated_weight", "calories", "protein", "carbs", "fat")


class MealEntrySerializer(serializers.ModelSerializer):
    food = FoodSerializer(read_only=True)
    packaged_food = PackagedFoodSerializer(read_only=True)
    components = MealComponentSerializer(many=True, read_only=True)

    class Meta:
        model = MealEntry
        fields = (
            "id",
            "log",
            "food",
            "packaged_food",
            "meal_time",
            "image_path",
            "source_type",
            "barcode",
            "search_query",
            "inference_job_id",
            "is_confirmed",
            "confirmed_at",
            "notes",
            "total_calories",
            "total_protein",
            "total_carbs",
            "total_fat",
            "total_weight",
            "components",
        )
        read_only_fields = ("id", "log", "meal_time", "confirmed_at")


class DailyLogSerializer(serializers.ModelSerializer):
    meals = MealEntrySerializer(many=True, read_only=True)

    class Meta:
        model = DailyLog
        fields = (
            "id",
            "date",
            "total_calories",
            "total_protein",
            "total_carbs",
            "total_fat",
            "total_weight",
            "meals",
        )


class MealFromInferenceSerializer(serializers.Serializer):
    job_id = serializers.CharField()
    date = serializers.DateField(required=False)
    notes = serializers.CharField(required=False, allow_blank=True)


class MealBarcodeSerializer(serializers.Serializer):
    barcode = serializers.CharField(max_length=64)
    date = serializers.DateField(required=False)
    servings = serializers.FloatField(required=False, min_value=0.01, default=1)


class MealSearchSerializer(serializers.Serializer):
    query = serializers.CharField(max_length=255)
    source_type = serializers.ChoiceField(choices=("text", "voice"), default="text")


class ManualComponentInputSerializer(serializers.Serializer):
    physical_data = serializers.PrimaryKeyRelatedField(queryset=IngredientPhysicalData.objects.all())
    component_name = serializers.CharField(max_length=255)
    volume = serializers.FloatField(min_value=0)


class ManualMealSerializer(serializers.Serializer):
    date = serializers.DateField(required=False)
    food = serializers.PrimaryKeyRelatedField(queryset=Food.objects.all(), required=False, allow_null=True)
    notes = serializers.CharField(required=False, allow_blank=True)
    components = ManualComponentInputSerializer(many=True, required=False)
    total_calories = serializers.FloatField(required=False, min_value=0)
    total_protein = serializers.FloatField(required=False, min_value=0)
    total_carbs = serializers.FloatField(required=False, min_value=0)
    total_fat = serializers.FloatField(required=False, min_value=0)
    total_weight = serializers.FloatField(required=False, min_value=0)


class MealUpdateSerializer(serializers.Serializer):
    notes = serializers.CharField(required=False, allow_blank=True)
    total_calories = serializers.FloatField(required=False, min_value=0)
    total_protein = serializers.FloatField(required=False, min_value=0)
    total_carbs = serializers.FloatField(required=False, min_value=0)
    total_fat = serializers.FloatField(required=False, min_value=0)
    total_weight = serializers.FloatField(required=False, min_value=0)


def get_or_create_daily_log(user, date_value=None):
    return DailyLog.objects.get_or_create(user=user, date=date_value or timezone.localdate())[0]


def refresh_daily_log(log):
    totals = log.meals.all()
    log.total_calories = sum(meal.total_calories for meal in totals)
    log.total_protein = sum(meal.total_protein for meal in totals)
    log.total_carbs = sum(meal.total_carbs for meal in totals)
    log.total_fat = sum(meal.total_fat for meal in totals)
    log.total_weight = sum(meal.total_weight for meal in totals)
    log.save(update_fields=["total_calories", "total_protein", "total_carbs", "total_fat", "total_weight"])
    return log
