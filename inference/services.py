import json
import difflib
import mimetypes
from io import BytesIO
from contextlib import ExitStack
from urllib.parse import urlsplit

import requests
from django.conf import settings
from rest_framework import status

from nutrients.models import IngredientPhysicalData


MAX_REMOTE_IMAGE_SIZE = 10 * 1024 * 1024


class AIServerError(Exception):
    """Chức năng: biểu diễn lỗi gọi AI server. Đầu vào: message/code/status. Đầu ra: exception chuẩn.

    `code` là phân loại lỗi ở tầng backend (timeout, bad_gateway, unavailable...),
    còn `ai_error_code` (nếu có) là error_code nghiệp vụ cụ thể do AI server trả về
    (vd. no_food_detected, no_ingredients_identified, no_segments_produced...) —
    giữ riêng để mobile/FE có thể hiển thị thông báo cụ thể theo loại lỗi AI,
    thay vì chỉ biết "gateway lỗi" chung.
    """

    def __init__(
        self,
        message,
        code="ai_server_error",
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail="",
        ai_error_code="",
    ):
        self.public_message = message
        self.code = code
        self.status_code = status_code
        self.detail = detail
        self.ai_error_code = ai_error_code
        super().__init__(message)


class TransientAIError(AIServerError):
    """Lỗi tạm thời (timeout, 5xx, mất kết nối) — AN TOÀN để retry."""


class PermanentAIError(AIServerError):
    """Lỗi cố định (4xx, payload sai) — retry chỉ tốn AI compute, KHÔNG nên retry."""


def call_ai_analysis_server(job):
    """Chức năng: gửi ảnh, metadata camera và depth map tới AI server. Đầu vào: InferenceJob. Đầu ra: JSON payload từ AI server."""
    if not settings.AI_SERVER_URL:
        raise AIServerError(
            "AI_SERVER_URL is not configured.",
            code="missing_config",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    url = f"{settings.AI_SERVER_URL}{settings.AI_SERVER_ANALYZE_PATH}"
    headers = {}
    if settings.AI_SERVER_API_KEY:
        headers["Authorization"] = f"Bearer {settings.AI_SERVER_API_KEY}"

    # The AI server reads depth-decode hints from camera_metadata["depth"]
    # (depth_unit/file_extension) — nest the job's depth_metadata there rather
    # than sending it as a separate, unread field.
    camera_metadata = dict(job.camera_metadata or {})
    if job.depth_map and job.depth_metadata:
        camera_metadata["depth"] = job.depth_metadata

    data = {
        "job_id": job.id,
        "camera_metadata": json.dumps(camera_metadata),
    }

    try:
        with ExitStack() as stack:
            image_name, image_file = _open_job_image(job, stack)
            files = {"image": (image_name, image_file)}
            if job.depth_map:
                depth_file = stack.enter_context(job.depth_map.open("rb"))
                files["depth_map"] = (job.depth_map.name, depth_file)

            response = requests.post(
                url,
                files=files,
                data=data,
                headers=headers,
                timeout=settings.AI_SERVER_TIMEOUT,
            )
        response.raise_for_status()
        return response.json()
    except requests.Timeout as exc:
        raise TransientAIError(
            "AI server request timed out.",
            code="timeout",
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
        ) from exc
    except requests.HTTPError as exc:
        response = exc.response
        upstream = response.status_code if response is not None else None
        ai_message, ai_error_code, ai_step = "", "", ""
        if response is not None:
            ai_message, ai_error_code, ai_step = _format_ai_error_detail(response)
        ai_error_code = _normalize_ai_error_code(ai_error_code, ai_step)
        public_message = ai_message or f"AI server returned HTTP {upstream or 'error'}."
        detail = f"error_code={ai_error_code}; step={ai_step}" if (ai_error_code or ai_step) else ""
        # 4xx from the AI server is a permanent problem with this request
        # (bad image/metadata, hoặc lỗi nghiệp vụ như no_food_detected/
        # no_ingredients_identified/no_segments_produced); retrying chỉ tốn AI
        # compute. 5xx / không có response là transient và đáng để retry.
        error_cls = (
            PermanentAIError if upstream is not None and 400 <= upstream < 500
            else TransientAIError
        )
        raise error_cls(
            public_message,
            code="bad_gateway",
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=detail,
            ai_error_code=ai_error_code,
        ) from exc
    except requests.RequestException as exc:
        raise TransientAIError(
            "AI server is unavailable.",
            code="unavailable",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        ) from exc
    except ValueError as exc:
        raise PermanentAIError(
            "AI server returned invalid JSON.",
            code="invalid_json",
            status_code=status.HTTP_502_BAD_GATEWAY,
        ) from exc


def _open_job_image(job, stack):
    """Chức năng: mở ảnh từ URL Cloudinary hoặc file legacy. Đầu vào: job/ExitStack. Đầu ra: tên file và file-like."""
    if job.image_url:
        try:
            response = requests.get(job.image_url, timeout=settings.AI_SERVER_TIMEOUT)
            response.raise_for_status()
        except requests.Timeout as exc:
            raise TransientAIError(
                "Image URL download timed out.",
                code="image_url_timeout",
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            ) from exc
        except requests.RequestException as exc:
            raise TransientAIError(
                "Could not download image URL.",
                code="image_url_unavailable",
                status_code=status.HTTP_502_BAD_GATEWAY,
            ) from exc

        content_type = response.headers.get("content-type", "").split(";")[0].lower()
        if content_type and not content_type.startswith("image/"):
            raise PermanentAIError(
                "Image URL must point to an image.",
                code="invalid_image_url_content_type",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        if len(response.content) > MAX_REMOTE_IMAGE_SIZE:
            raise PermanentAIError(
                "Image URL file is too large.",
                code="image_url_too_large",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        path = urlsplit(job.image_url).path
        extension = mimetypes.guess_extension(content_type) if content_type else ""
        if not extension and "." in path:
            extension = path[path.rfind(".") :]
        filename = f"{job.id}{extension or '.jpg'}"
        return filename, BytesIO(response.content)

    if job.image:
        return job.image.name, stack.enter_context(job.image.open("rb"))

    raise PermanentAIError(
        "Inference job image URL is missing.",
        code="missing_image_url",
        status_code=status.HTTP_400_BAD_REQUEST,
    )


def _format_ai_error_detail(response):
    """Chức năng: rút gọn lỗi JSON từ AI server. Đầu vào: requests.Response.
    Đầu ra: (message, ai_error_code, step). AI server (FastAPI) trả lỗi dạng
    {"detail": {"error_code": ..., "message": ..., "context": {"step": ...}}} -
    error_code là mã lỗi nghiệp vụ cụ thể (vd. no_food_detected,
    no_ingredients_identified, no_segments_produced...) để mobile/FE hiển thị
    thông báo riêng cho từng loại lỗi thay vì chỉ một message chung."""
    try:
        payload = response.json()
    except ValueError:
        return response.text[:1000], "", ""

    detail = payload.get("detail")
    if isinstance(detail, dict):
        message = detail.get("message") or payload.get("message") or response.text
        ai_error_code = detail.get("error_code") or ""
        context = detail.get("context")
        step = context.get("step") if isinstance(context, dict) else None
        return str(message)[:1000], ai_error_code, step or ""

    if detail:
        return str(detail)[:1000], "", ""
    return response.text[:1000], "", ""


def _normalize_ai_error_code(ai_error_code, step):
    """Chức năng: gộp các lỗi depth (estimate/client) thành 1 mã rõ nghĩa cho FE/mobile.
    Đầu vào: error_code thô + step từ AI server. Đầu ra: error_code đã chuẩn hóa.

    AI server dùng error_code chung ("inference_error"/"validation_error") cho mọi
    bước inference, chỉ phân biệt bước cụ thể qua context.step ("depth"/"depth_client").
    Mobile/FE cần 1 mã duy nhất để map sang thông báo "ước tính độ sâu thất bại" mà
    không phải tự suy luận từ step ở từng client.
    """
    if ai_error_code in ("inference_error", "validation_error") and (step or "").startswith("depth"):
        return "depth_estimation_failed"
    return ai_error_code


def find_best_ingredient_match(target_name, ingredients, similarity_cutoff=0.6):
    """Chức năng: match tên nguyên liệu AI với DB backend. Đầu vào: tên và queryset/list Ingredient. Đầu ra: Ingredient hoặc None."""
    target_name = (target_name or "").lower().strip()
    if not target_name:
        return None

    db_map = {}
    for ingredient in ingredients:
        for value in (ingredient.en_name, ingredient.vi_name):
            normalized = (value or "").lower().strip()
            if normalized:
                db_map[normalized] = ingredient

    if target_name in db_map:
        return db_map[target_name]

    for normalized_name, ingredient in db_map.items():
        if normalized_name in target_name or target_name in normalized_name:
            return ingredient

    best_matches = difflib.get_close_matches(
        target_name,
        list(db_map.keys()),
        n=1,
        cutoff=similarity_cutoff,
    )
    return db_map[best_matches[0]] if best_matches else None


def calculate_component_nutrition(component, physical_data=None):
    """Chức năng: tính khối lượng và macro từ volume + IngredientPhysicalData. Đầu vào: component AI. Đầu ra: component chuẩn hóa."""
    volume = float(component.get("volume") or component.get("volume_cm3") or 0)
    if not physical_data:
        return {
            "component_id": component.get("component_id") or component.get("instance_id") or "",
            "component_name": component.get("component_name") or "",
            "physical_data_id": "",
            "mask_path": component.get("mask_path") or "",
            "volume": volume,
            "weight": 0.0,
            "calories": 0.0,
            "protein": 0.0,
            "carbs": 0.0,
            "fat": 0.0,
        }

    weight = volume * float(physical_data.density or 0)
    return {
        "component_id": component.get("component_id") or component.get("instance_id") or "",
        "component_name": component.get("component_name") or physical_data.vi_name,
        "physical_data_id": physical_data.id,
        "mask_path": component.get("mask_path") or "",
        "volume": round(volume, 2),
        "weight": round(weight, 2),
        "calories": round(weight * float(physical_data.cal_per_100g or 0) / 100, 2),
        "protein": round(weight * float(physical_data.protein_per_100g or 0) / 100, 2),
        "carbs": round(weight * float(physical_data.carb_per_100g or 0) / 100, 2),
        "fat": round(weight * float(physical_data.fat_per_100g or 0) / 100, 2),
    }


def normalize_ai_result(payload):
    """Chức năng: chuẩn hóa kết quả AI và tính dinh dưỡng tại backend. Đầu vào: payload AI. Đầu ra: tổng dinh dưỡng và components."""
    components = payload.get("components") or []
    ingredients = list(IngredientPhysicalData.objects.all())
    normalized_components = [
        normalize_ai_component(component, ingredients)
        for component in components
    ]
    totals = {
        "calories": sum(component["calories"] for component in normalized_components),
        "protein": sum(component["protein"] for component in normalized_components),
        "carbs": sum(component["carbs"] for component in normalized_components),
        "fat": sum(component["fat"] for component in normalized_components),
        "weight": sum(component["weight"] for component in normalized_components),
    }
    return {
        "total_calories": round(totals["calories"], 2),
        "total_protein": round(totals["protein"], 2),
        "total_carbs": round(totals["carbs"], 2),
        "total_fat": round(totals["fat"], 2),
        "total_weight": round(totals["weight"], 2),
        "components": normalized_components,
        "latency_ms": int(payload.get("latency_ms") or 0),
        "model_version": payload.get("model_version") or "",
    }


def normalize_ai_component(component, ingredients=None):
    """Chức năng: chuẩn hóa một thành phần AI và tính dinh dưỡng. Đầu vào: component AI. Đầu ra: dict component."""
    ingredients = ingredients if ingredients is not None else list(IngredientPhysicalData.objects.all())
    physical_data = find_best_ingredient_match(component.get("component_name"), ingredients)
    return calculate_component_nutrition(component, physical_data)
