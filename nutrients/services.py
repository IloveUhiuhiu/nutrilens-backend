import logging

from django.conf import settings
from django.utils import timezone

from .clients import ExternalLookupError, OpenFoodFactsClient, USDAClient
from .models import Food, PackagedFood
from .query_translation import (
    QueryTranslationError,
    attach_original_vietnamese_fields,
    should_translate_query,
    translate_food_description_to_vietnamese,
    translate_food_query_to_english,
    translate_packaged_food_name_to_vietnamese,
    translate_usda_results_to_vietnamese,
)

logger = logging.getLogger(__name__)


def _to_float(value, default=0):
    """Chức năng: ép giá trị về float. Đầu vào: value và default. Đầu ra: số float an toàn."""
    if value in (None, ""):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def lookup_open_food_facts_barcode(barcode):
    """Chức năng: tra barcode trên Open Food Facts. Đầu vào: barcode. Đầu ra: payload sản phẩm hoặc None."""
    return OpenFoodFactsClient().lookup_barcode(barcode)


def save_packaged_food_from_open_food_facts(barcode, payload):
    """Chức năng: lưu sản phẩm barcode vào local. Đầu vào: barcode và payload OFF. Đầu ra: PackagedFood."""
    product = payload["product"]
    nutriments = product.get("nutriments") or {}

    serving_size = _to_float(product.get("serving_quantity"), 100)
    serving_unit = product.get("serving_quantity_unit") or "g"
    scale = serving_size / 100 if serving_unit.lower() in ("g", "ml") else 1

    cal_per_serving = _to_float(nutriments.get("energy-kcal_serving"))
    if not cal_per_serving:
        cal_per_serving = _to_float(nutriments.get("energy-kcal_100g")) * scale

    protein_per_serving = _to_float(nutriments.get("proteins_serving"))
    if not protein_per_serving:
        protein_per_serving = _to_float(nutriments.get("proteins_100g")) * scale

    carb_per_serving = _to_float(nutriments.get("carbohydrates_serving"))
    if not carb_per_serving:
        carb_per_serving = _to_float(nutriments.get("carbohydrates_100g")) * scale

    fat_per_serving = _to_float(nutriments.get("fat_serving"))
    if not fat_per_serving:
        fat_per_serving = _to_float(nutriments.get("fat_100g")) * scale

    raw_name = product.get("product_name") or product.get("generic_name") or f"Barcode {barcode}"
    try:
        translated_name, _ = translate_packaged_food_name_to_vietnamese(raw_name)
    except QueryTranslationError:
        logger.warning("Packaged food name translation failed for barcode=%s", barcode, exc_info=True)
        translated_name = raw_name

    packaged_food, _ = PackagedFood.objects.update_or_create(
        barcode=barcode,
        defaults={
            "name": translated_name,
            "brand": product.get("brands") or "",
            "serving_size": serving_size,
            "serving_unit": serving_unit,
            "cal_per_serving": round(cal_per_serving, 2),
            "fat_per_serving": round(fat_per_serving, 2),
            "carb_per_serving": round(carb_per_serving, 2),
            "protein_per_serving": round(protein_per_serving, 2),
            "image_url": product.get("image_url"),
            "external_source": "open_food_facts",
            "external_id": barcode,
            "raw_payload": payload,
            "last_synced_at": timezone.now(),
            "is_active": True,
        },
    )
    return packaged_food


def lookup_and_save_barcode(barcode):
    """Chức năng: tra barcode ngoài rồi lưu local. Đầu vào: barcode. Đầu ra: PackagedFood hoặc None."""
    payload = lookup_open_food_facts_barcode(barcode)
    if not payload:
        return None
    return save_packaged_food_from_open_food_facts(barcode, payload)


def ensure_vietnamese_packaged_food_name(packaged_food):
    """Chức năng: đảm bảo tên sản phẩm barcode hiển thị bằng tiếng Việt trước khi trả về client."""
    if not packaged_food or should_translate_query(packaged_food.name):
        return packaged_food
    try:
        translated_name, _ = translate_packaged_food_name_to_vietnamese(packaged_food.name)
    except QueryTranslationError:
        logger.warning(
            "Packaged food name translation failed for barcode=%s", packaged_food.barcode, exc_info=True
        )
        return packaged_food
    if translated_name and translated_name != packaged_food.name:
        packaged_food.name = translated_name
        packaged_food.save(update_fields=["name", "updated_at"])
    return packaged_food


def get_or_lookup_barcode(barcode):
    """Chức năng: tra barcode local trước, thiếu thì gọi OFF và lưu. Đầu vào: barcode. Đầu ra: PackagedFood hoặc None."""
    packaged_food = PackagedFood.objects.filter(barcode=barcode, is_active=True).first()
    if packaged_food:
        return ensure_vietnamese_packaged_food_name(packaged_food)
    packaged_food = lookup_and_save_barcode(barcode)
    return ensure_vietnamese_packaged_food_name(packaged_food)


def search_usda_foods(query, page_size=20, page_number=1, data_types=None):
    """Chức năng: tìm món ăn trên USDA. Đầu vào: query, phân trang, data types. Đầu ra: payload USDA."""
    return USDAClient().search_foods(
        query,
        page_size=page_size,
        page_number=page_number,
        data_types=data_types,
    )


def get_usda_food(fdc_id):
    """Chức năng: lấy chi tiết thực phẩm USDA. Đầu vào: fdc_id. Đầu ra: payload chi tiết USDA."""
    return USDAClient().get_food(fdc_id)


def _nutrient_value(food_payload, nutrient_names):
    """Chức năng: lấy giá trị nutrient từ payload. Đầu vào: payload và tên nutrient. Đầu ra: số dinh dưỡng."""
    nutrients = food_payload.get("foodNutrients") or []
    lowered = {name.lower() for name in nutrient_names}
    for item in nutrients:
        name = (item.get("nutrientName") or item.get("nutrient", {}).get("name") or "").lower()
        if name in lowered:
            return _to_float(item.get("value") or item.get("amount"))
    return 0


def normalize_usda_search_result(item):
    """Chức năng: chuẩn hóa kết quả search USDA. Đầu vào: item USDA. Đầu ra: dict dùng cho API."""
    fdc_id = str(item.get("fdcId") or "")
    description = item.get("description") or ""
    brand = item.get("brandOwner") or item.get("brandName") or ""
    return {
        "fdc_id": fdc_id,
        "description": description,
        "brand": brand,
        "data_type": item.get("dataType") or "",
        "category": item.get("foodCategory") or "",
        "cal_per_100g": _nutrient_value(item, ["Energy"]),
        "protein_per_100g": _nutrient_value(item, ["Protein"]),
        "carb_per_100g": _nutrient_value(item, ["Carbohydrate, by difference"]),
        "fat_per_100g": _nutrient_value(item, ["Total lipid (fat)"]),
    }


def save_food_from_usda_payload(food_payload):
    """Chức năng: lưu thực phẩm USDA vào local. Đầu vào: payload chi tiết USDA. Đầu ra: Food."""
    fdc_id = str(food_payload.get("fdcId") or "")
    description = food_payload.get("description") or f"USDA Food {fdc_id}"
    category = food_payload.get("foodCategory", {}).get("description") if isinstance(food_payload.get("foodCategory"), dict) else food_payload.get("foodCategory")

    try:
        vi_name, _ = translate_food_description_to_vietnamese(description)
    except QueryTranslationError:
        logger.warning("Food description translation failed for fdc_id=%s", fdc_id, exc_info=True)
        vi_name = description

    food, _ = Food.objects.update_or_create(
        fdc_id=fdc_id,
        defaults={
            "vi_name": vi_name,
            "en_name": description,
            "category": category or food_payload.get("dataType") or "USDA",
            "external_source": "usda",
            "raw_payload": food_payload,
            "last_synced_at": timezone.now(),
        },
    )
    return food


def search_usda_top_foods(query, limit=5):
    """Chức năng: tìm top món USDA bên ngoài. Đầu vào: query và limit. Đầu ra: kết quả top USDA chưa lưu local."""
    original_query = query
    try:
        translated_query, translation_source = translate_food_query_to_english(query)
    except QueryTranslationError:
        logger.warning("Food query translation failed for query=%r", query, exc_info=True)
        translated_query = query
        translation_source = "original_translation_failed"

    data_types = settings.USDA_SEARCH_DATA_TYPES
    payload = search_usda_foods(
        translated_query,
        page_size=limit,
        page_number=1,
        data_types=data_types,
    )
    results = []
    for item in payload.get("foods", [])[:limit]:
        if not item.get("fdcId"):
            continue
        result = normalize_usda_search_result(item)
        result["unit"] = "gram"
        result["source"] = "usda"
        results.append(result)

    try:
        results, result_translation_source = translate_usda_results_to_vietnamese(results)
    except QueryTranslationError:
        logger.warning("USDA result translation failed for query=%r", translated_query, exc_info=True)
        results = attach_original_vietnamese_fields(results)
        result_translation_source = "original_translation_failed"

    return {
        "source": "usda",
        "query": translated_query,
        "original_query": original_query,
        "translation_source": translation_source,
        "result_translation_source": result_translation_source,
        "data_types": list(data_types),
        "total_hits": payload.get("totalHits", len(results)),
        "current_page": 1,
        "results": results,
    }


def ensure_vietnamese_food_name(food):
    """Chức năng: đảm bảo tên món USDA hiển thị bằng tiếng Việt trước khi trả về client."""
    if not food or should_translate_query(food.vi_name):
        return food
    try:
        translated_name, _ = translate_food_description_to_vietnamese(food.en_name or food.vi_name)
    except QueryTranslationError:
        logger.warning("Food name translation failed for fdc_id=%s", food.fdc_id, exc_info=True)
        return food
    if translated_name and translated_name != food.vi_name:
        food.vi_name = translated_name
        food.save(update_fields=["vi_name"])
    return food


def get_or_lookup_usda_food(fdc_id):
    """Chức năng: gọi USDA detail và lưu Food được chọn. Đầu vào: fdc_id. Đầu ra: Food."""
    from .models import Food

    food = Food.objects.filter(fdc_id=fdc_id).first()
    if food:
        return ensure_vietnamese_food_name(food)
    payload = get_usda_food(fdc_id)
    food = save_food_from_usda_payload(payload)
    return ensure_vietnamese_food_name(food)
