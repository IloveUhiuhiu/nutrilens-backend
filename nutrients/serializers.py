from rest_framework import serializers
from .models import Food, HealthAdviceRule, IngredientPhysicalData, PackagedFood


class FoodSerializer(serializers.ModelSerializer):
    class Meta:
        model = Food
        fields = ("id", "vi_name", "en_name", "fdc_id", "category", "image_url")


class IngredientPhysicalDataSerializer(serializers.ModelSerializer):
    class Meta:
        model = IngredientPhysicalData
        fields = (
            "id",
            "vi_name",
            "en_name",
            "density",
            "cal_per_100g",
            "fat_per_100g",
            "carb_per_100g",
            "protein_per_100g",
            "fdc_id_ref",
        )


class HealthAdviceRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = HealthAdviceRule
        fields = ("id", "min_percent", "max_percent", "alert_level", "advice_content")


class PackagedFoodSerializer(serializers.ModelSerializer):
    class Meta:
        model = PackagedFood
        fields = (
            "id",
            "barcode",
            "name",
            "brand",
            "serving_size",
            "serving_unit",
            "cal_per_serving",
            "fat_per_serving",
            "carb_per_serving",
            "protein_per_serving",
            "image_url",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")
