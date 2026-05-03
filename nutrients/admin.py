from django.contrib import admin
from .models import IngredientPhysicalData, Food, HealthAdviceRule

@admin.register(IngredientPhysicalData)
class IngredientAdmin(admin.ModelAdmin):
    list_display = ('id', 'vi_name', 'density', 'cal_per_100g', 'protein_per_100g')
    search_fields = ('vi_name', 'en_name', 'fdc_id_ref')
    list_filter = ('density',)

@admin.register(Food)
class FoodAdmin(admin.ModelAdmin):
    list_display = ('vi_name', 'fdc_id', 'category')
    search_fields = ('vi_name', 'fdc_id')

@admin.register(HealthAdviceRule)
class RuleAdmin(admin.ModelAdmin):
    list_display = ('alert_level', 'min_percent', 'max_percent')