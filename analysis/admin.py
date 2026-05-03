from django.contrib import admin
from .models import DailyLog, MealEntry, MealComponent

class MealComponentInline(admin.TabularInline):
    model = MealComponent
    extra = 1

@admin.register(MealEntry)
class MealEntryAdmin(admin.ModelAdmin):
    list_display = ('id', 'log', 'total_calories', 'meal_time')
    inlines = [MealComponentInline]

@admin.register(DailyLog)
class DailyLogAdmin(admin.ModelAdmin):
    list_display = ('date', 'user', 'total_calories', 'total_weight')
    list_filter = ('date', 'user')

admin.site.register(MealComponent)