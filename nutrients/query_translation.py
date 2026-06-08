import logging
import json
import re

from django.conf import settings


logger = logging.getLogger(__name__)

VIETNAMESE_CHAR_PATTERN = re.compile(
    r"[ăâđêôơưáàảãạấầẩẫậắằẳẵặéèẻẽẹếềểễệíìỉĩị"
    r"óòỏõọốồổỗộớờởỡợúùủũụứừửữựýỳỷỹỵ]",
    re.IGNORECASE,
)


class QueryTranslationError(Exception):
    """Lỗi dịch query tìm kiếm thực phẩm."""


def should_translate_query(query):
    """Chức năng: xác định query có cần dịch sang tiếng Anh không."""
    return bool(VIETNAMESE_CHAR_PATTERN.search(query or ""))


def clean_translation(value):
    """Chức năng: chuẩn hóa output model thành một query tiếng Anh ngắn."""
    value = (value or "").strip().strip('"').strip("'")
    value = value.replace("\n", " ").strip()
    return re.sub(r"\s+", " ", value)


def parse_json_array_response(value):
    """Chức năng: parse JSON array kể cả khi model bọc trong markdown code fence."""
    value = (value or "").strip()
    if value.startswith("```"):
        value = re.sub(r"^```(?:json)?", "", value, flags=re.IGNORECASE).strip()
        value = re.sub(r"```$", "", value).strip()
    start = value.find("[")
    end = value.rfind("]")
    if start != -1 and end != -1:
        value = value[start : end + 1]
    return json.loads(value)


def attach_original_vietnamese_fields(results):
    """Chức năng: đảm bảo response luôn có field tiếng Việt, kể cả khi chưa dịch được."""
    return [
        {
            **result,
            "description_en": result.get("description_en") or result.get("description", ""),
            "category_en": result.get("category_en") or result.get("category", ""),
            "description_vi": result.get("description", ""),
            "category_vi": result.get("category", ""),
        }
        for result in results
    ]


def translate_food_query_to_english(query):
    """Chức năng: dịch query món/nguyên liệu tiếng Việt sang tiếng Anh cho USDA."""
    query = (query or "").strip()
    if not query or not should_translate_query(query):
        return query, "original"

    if not settings.GITHUB_MODELS_TOKEN:
        logger.warning("GITHUB_TOKEN/GITHUB_MODELS_TOKEN is not configured; using original USDA query.")
        return query, "original_missing_token"

    try:
        from openai import OpenAI
    except ImportError as exc:
        raise QueryTranslationError("OpenAI SDK is not installed. Run: pip install openai") from exc

    client = OpenAI(
        base_url=settings.GITHUB_MODELS_ENDPOINT,
        api_key=settings.GITHUB_MODELS_TOKEN,
        timeout=settings.GITHUB_MODELS_TRANSLATION_TIMEOUT,
    )
    try:
        response = client.chat.completions.create(
            model=settings.GITHUB_MODELS_TRANSLATION_MODEL,
            temperature=0,
            top_p=1,
            max_tokens=40,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Translate Vietnamese food search queries into concise English USDA FoodData Central "
                        "search terms. Return only the translated query, no punctuation, no explanation. "
                        "Prefer ingredient/common food names over full sentences."
                    ),
                },
                {"role": "user", "content": query},
            ],
        )
        translated_query = clean_translation(response.choices[0].message.content)
    except Exception as exc:
        raise QueryTranslationError("GitHub Models translation failed.") from exc
    return translated_query or query, "github_models"


PACKAGED_FOOD_NAME_PROMPT = (
    "Translate this exact packaged food/product name into a natural, appetizing, "
    "and concise Vietnamese food title suitable for a health logging UI. "
    "Avoid literal machine translations."
)


def translate_packaged_food_name_to_vietnamese(name):
    """Chức năng: dịch tên sản phẩm đóng gói sang tiếng Việt tự nhiên cho UI ghi nhận bữa ăn."""
    name = (name or "").strip()
    if not name:
        return name, "original"

    if not settings.GITHUB_MODELS_TOKEN:
        logger.warning(
            "GITHUB_TOKEN/GITHUB_MODELS_TOKEN is not configured; using original packaged food name."
        )
        return name, "original_missing_token"

    try:
        from openai import OpenAI
    except ImportError as exc:
        raise QueryTranslationError("OpenAI SDK is not installed. Run: pip install openai") from exc

    client = OpenAI(
        base_url=settings.GITHUB_MODELS_ENDPOINT,
        api_key=settings.GITHUB_MODELS_TOKEN,
        timeout=settings.GITHUB_MODELS_TRANSLATION_TIMEOUT,
    )
    try:
        response = client.chat.completions.create(
            model=settings.GITHUB_MODELS_TRANSLATION_MODEL,
            temperature=0,
            top_p=1,
            max_tokens=80,
            messages=[
                {"role": "system", "content": PACKAGED_FOOD_NAME_PROMPT},
                {"role": "user", "content": name},
            ],
        )
        translated_name = clean_translation(response.choices[0].message.content)
    except Exception as exc:
        raise QueryTranslationError("GitHub Models packaged food translation failed.") from exc

    return translated_name or name, "github_models"


def translate_food_description_to_vietnamese(description):
    """Chức năng: dịch tên món USDA sang tiếng Việt tự nhiên cho UI ghi nhận bữa ăn."""
    description = (description or "").strip()
    if not description:
        return description, "original"

    if should_translate_query(description):
        return description, "original"

    if not settings.GITHUB_MODELS_TOKEN:
        return description, "original_missing_token"

    try:
        from openai import OpenAI
    except ImportError as exc:
        raise QueryTranslationError("OpenAI SDK is not installed. Run: pip install openai") from exc

    client = OpenAI(
        base_url=settings.GITHUB_MODELS_ENDPOINT,
        api_key=settings.GITHUB_MODELS_TOKEN,
        timeout=settings.GITHUB_MODELS_TRANSLATION_TIMEOUT,
    )
    try:
        response = client.chat.completions.create(
            model=settings.GITHUB_MODELS_TRANSLATION_MODEL,
            temperature=0,
            top_p=1,
            max_tokens=80,
            messages=[
                {"role": "system", "content": PACKAGED_FOOD_NAME_PROMPT},
                {"role": "user", "content": description},
            ],
        )
        translated_name = clean_translation(response.choices[0].message.content)
    except Exception as exc:
        raise QueryTranslationError("GitHub Models food description translation failed.") from exc

    return translated_name or description, "github_models"


def translate_usda_results_to_vietnamese(results):
    """Chức năng: dịch batch description/category USDA sang tiếng Việt để hiển thị."""
    if not results:
        return results, "original"
    if not settings.GITHUB_MODELS_TOKEN:
        return attach_original_vietnamese_fields(results), "original_missing_token"

    try:
        from openai import OpenAI
    except ImportError as exc:
        raise QueryTranslationError("OpenAI SDK is not installed. Run: pip install openai") from exc

    source_items = [
        {
            "index": index,
            "description": result.get("description", ""),
            "category": result.get("category", ""),
        }
        for index, result in enumerate(results)
    ]
    client = OpenAI(
        base_url=settings.GITHUB_MODELS_ENDPOINT,
        api_key=settings.GITHUB_MODELS_TOKEN,
        timeout=settings.GITHUB_MODELS_TRANSLATION_TIMEOUT,
    )
    try:
        response = client.chat.completions.create(
            model=settings.GITHUB_MODELS_TRANSLATION_MODEL,
            temperature=0,
            top_p=1,
            max_tokens=900,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Translate USDA food search result fields to Vietnamese. "
                        "Return only valid JSON array. Each object must contain index, "
                        "description_vi, category_vi. Keep brand names and measurements unchanged."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(source_items, ensure_ascii=False),
                },
            ],
        )
        translated_items = parse_json_array_response(response.choices[0].message.content)
    except Exception as exc:
        raise QueryTranslationError("GitHub Models result translation failed.") from exc

    translations_by_index = {
        item.get("index"): item
        for item in translated_items
        if isinstance(item, dict)
    }
    translated_results = []
    for index, result in enumerate(results):
        translated = translations_by_index.get(index, {})
        description_en = result.get("description", "")
        category_en = result.get("category", "")
        description_vi = clean_translation(translated.get("description_vi")) or description_en
        category_vi = clean_translation(translated.get("category_vi")) or category_en
        result = {
            **result,
            "description": description_vi,
            "category": category_vi,
            "description_en": description_en,
            "category_en": category_en,
            "description_vi": description_vi,
            "category_vi": category_vi,
        }
        translated_results.append(result)
    return translated_results, "github_models"
