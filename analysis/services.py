from django.utils import timezone

from inference.models import InferenceJob
from nutrients.models import IngredientPhysicalData
from nutrients.services import get_or_lookup_barcode, get_or_lookup_usda_food

from .models import MealComponent, MealEntry
from .serializers import get_or_create_daily_log, refresh_daily_log


class AnalysisServiceError(Exception):
    """Chức năng: lỗi nghiệp vụ analysis. Đầu vào: message, field. Đầu ra: exception có field lỗi."""

    def __init__(self, message, field="detail"):
        self.message = message
        self.field = field
        super().__init__(message)


def format_quantity(value):
    """Chức năng: format số lượng hiển thị. Đầu vào: số. Đầu ra: chuỗi không có .0 thừa."""
    number = float(value or 0)
    return str(int(number)) if number.is_integer() else f"{number:g}"


def create_meal_from_totals(log, **kwargs):
    """Chức năng: tạo meal từ tổng dinh dưỡng. Đầu vào: DailyLog và các field meal. Đầu ra: MealEntry đã lưu."""
    meal = MealEntry.objects.create(log=log, confirmed_at=timezone.now(), **kwargs)
    refresh_daily_log(log)
    return meal


def create_meal_from_inference(user, job_id, date=None, notes=""):
    """Chức năng: tạo meal từ job AI. Đầu vào: user, job_id, date, notes. Đầu ra: MealEntry."""
    job = InferenceJob.objects.filter(id=job_id, user=user).first()
    if not job:
        raise AnalysisServiceError("Inference job not found.", field="job_id")
    if job.status != "succeeded" or not hasattr(job, "result"):
        raise AnalysisServiceError("Inference result is not ready.", field="job_id")

    log = get_or_create_daily_log(user, date)
    result = job.result
    meal = create_meal_from_totals(
        log,
        source_type="image",
        image_path=job.image,
        inference_job_id=job.id,
        notes=notes,
        total_calories=result.total_calories,
        total_protein=result.total_protein,
        total_carbs=result.total_carbs,
        total_fat=result.total_fat,
        total_weight=result.total_weight,
    )
    create_components_from_inference_result(meal, result.components)
    return meal


def create_components_from_inference_result(meal, components):
    """Chức năng: tạo MealComponent từ components AI. Đầu vào: meal và components. Đầu ra: số component tạo được."""
    created_count = 0
    for component in components or []:
        physical_data_id = component.get("physical_data_id")
        volume = component.get("volume") or 0
        if not physical_data_id or not volume:
            continue
        physical_data = IngredientPhysicalData.objects.filter(id=physical_data_id).first()
        if not physical_data:
            continue
        MealComponent.objects.create(
            meal_entry=meal,
            physical_data=physical_data,
            component_name=component.get("component_name") or physical_data.vi_name,
            mask_path=component.get("mask_path") or None,
            volume=volume,
            calculated_weight=component.get("weight") or 0,
            calories=component.get("calories") or 0,
            protein=component.get("protein") or 0,
            carbs=component.get("carbs") or 0,
            fat=component.get("fat") or 0,
        )
        created_count += 1
    return created_count


def create_meal_from_barcode(user, barcode, servings=1, date=None):
    """Chức năng: tạo meal từ barcode. Đầu vào: user, barcode, servings, date. Đầu ra: MealEntry."""
    packaged_food = get_or_lookup_barcode(barcode)
    if not packaged_food:
        raise AnalysisServiceError("Packaged food not found.", field="barcode")

    log = get_or_create_daily_log(user, date)
    return create_meal_from_totals(
        log,
        packaged_food=packaged_food,
        source_type="barcode",
        barcode=packaged_food.barcode,
        serving_amount=servings,
        serving_unit_id="serving",
        serving_unit_label=f"{format_quantity(packaged_food.serving_size)} {packaged_food.serving_unit}",
        total_calories=packaged_food.cal_per_serving * servings,
        total_protein=packaged_food.protein_per_serving * servings,
        total_carbs=packaged_food.carb_per_serving * servings,
        total_fat=packaged_food.fat_per_serving * servings,
        total_weight=packaged_food.serving_size * servings,
    )


def nutrient_value_from_payload(payload, *names):
    """Chức năng: lấy nutrient từ payload USDA. Đầu vào: payload và tên nutrient. Đầu ra: giá trị số."""
    nutrients = {item.get("nutrient", {}).get("name", item.get("nutrientName", "")): item for item in payload.get("foodNutrients", [])}
    lowered = {name.lower() for name in names}
    for name, item in nutrients.items():
        if name.lower() in lowered:
            return float(item.get("amount") or item.get("value") or 0)
    return 0


def create_meal_from_usda(user, fdc_id, grams, date=None, source_type="text", search_query=""):
    """Chức năng: tạo meal từ USDA Food. Đầu vào: user, fdc_id, grams. Đầu ra: MealEntry."""
    food = get_or_lookup_usda_food(fdc_id)
    payload = food.raw_payload or {}
    scale = grams / 100
    log = get_or_create_daily_log(user, date)
    return create_meal_from_totals(
        log,
        food=food,
        source_type=source_type,
        search_query=search_query,
        serving_amount=grams,
        serving_unit_id="gram",
        serving_unit_label="gram",
        total_calories=nutrient_value_from_payload(payload, "Energy") * scale,
        total_protein=nutrient_value_from_payload(payload, "Protein") * scale,
        total_carbs=nutrient_value_from_payload(payload, "Carbohydrate, by difference") * scale,
        total_fat=nutrient_value_from_payload(payload, "Total lipid (fat)") * scale,
        total_weight=grams,
    )


def create_manual_meal(user, data):
    """Chức năng: tạo meal thủ công. Đầu vào: user và validated data. Đầu ra: MealEntry."""
    log = get_or_create_daily_log(user, data.get("date"))
    meal = MealEntry.objects.create(
        log=log,
        food=data.get("food"),
        source_type="manual",
        notes=data.get("notes", ""),
        confirmed_at=timezone.now(),
        total_calories=data.get("total_calories", 0),
        total_protein=data.get("total_protein", 0),
        total_carbs=data.get("total_carbs", 0),
        total_fat=data.get("total_fat", 0),
        total_weight=data.get("total_weight", 0),
    )

    for component in data.get("components", []):
        MealComponent.objects.create(meal_entry=meal, **component)

    if meal.components.exists():
        meal.total_calories = sum(component.calories for component in meal.components.all())
        meal.total_protein = sum(component.protein for component in meal.components.all())
        meal.total_carbs = sum(component.carbs for component in meal.components.all())
        meal.total_fat = sum(component.fat for component in meal.components.all())
        meal.total_weight = sum(component.calculated_weight for component in meal.components.all())
        meal.save(update_fields=["total_calories", "total_protein", "total_carbs", "total_fat", "total_weight"])

    refresh_daily_log(log)
    return meal
