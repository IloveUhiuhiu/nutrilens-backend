import json
from urllib.parse import urlsplit

from rest_framework import serializers
from .models import InferenceFeedback, InferenceJob, InferenceResult


class ImageOrUrlField(serializers.Field):
    def to_internal_value(self, value):
        if hasattr(value, "read"):
            content_type = getattr(value, "content_type", "")
            if content_type and not content_type.startswith("image/"):
                raise serializers.ValidationError("Uploaded file must be an image.")
            return value

        if isinstance(value, str):
            scheme = urlsplit(value).scheme
            if scheme not in ("http", "https"):
                raise serializers.ValidationError(
                    "Only http and https image URLs are supported."
                )
            return value

        raise serializers.ValidationError("Image must be an upload file or URL.")

    def to_representation(self, value):
        return value


class InferenceJobCreateSerializer(serializers.ModelSerializer):
    image = ImageOrUrlField(write_only=True)
    camera_metadata = serializers.JSONField()

    class Meta:
        model = InferenceJob
        fields = ("image", "camera_metadata")

    def validate_camera_metadata(self, value):
        """Chức năng: kiểm tra metadata camera. Đầu vào: dict hoặc JSON string. Đầu ra: dict hợp lệ."""
        metadata = self._parse_json_object(value, "camera_metadata")
        if "distance_cm" in metadata and "camera_height_cm" not in metadata and "camera_height_mm" not in metadata:
            metadata["camera_height_cm"] = metadata["distance_cm"]
        has_camera_height = "camera_height_cm" in metadata or "camera_height_mm" in metadata
        has_pixel_area = "pixel_area_cm2" in metadata
        has_intrinsics = "fx" in metadata and "fy" in metadata
        if not has_camera_height:
            raise serializers.ValidationError("camera_height_cm or camera_height_mm is required.")
        if not has_pixel_area and not has_intrinsics:
            raise serializers.ValidationError("pixel_area_cm2 or camera intrinsics fx/fy is required.")
        return metadata

    def _parse_json_object(self, value, field_name):
        """Chức năng: parse JSON object từ multipart. Đầu vào: value và field. Đầu ra: dict hoặc lỗi."""
        if value in (None, ""):
            return {}
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except json.JSONDecodeError as exc:
                raise serializers.ValidationError("Must be a valid JSON object.") from exc
        if not isinstance(value, dict):
            raise serializers.ValidationError(f"{field_name} must be a JSON object.")
        return value

    def create(self, validated_data):
        image = validated_data.pop("image")
        if isinstance(image, str):
            validated_data["image_url"] = image
        else:
            validated_data["image"] = image
        return super().create(validated_data)


class InferenceResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = InferenceResult
        fields = (
            "id",
            "job",
            "total_calories",
            "total_protein",
            "total_carbs",
            "total_fat",
            "total_weight",
            "components",
            "created_at",
        )
        read_only_fields = fields


class InferenceJobSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()
    result = InferenceResultSerializer(read_only=True)

    def get_image(self, obj):
        """Chức năng: trả URL ảnh gốc nếu có. Đầu vào: InferenceJob. Đầu ra: URL ảnh."""
        if obj.image_url:
            return obj.image_url
        if obj.image:
            return obj.image.url
        return None

    class Meta:
        model = InferenceJob
        fields = (
            "id",
            "image",
            "camera_metadata",
            "status",
            "model_version",
            "latency_ms",
            "error_message",
            "raw_output",
            "result",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class InferenceFeedbackCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = InferenceFeedback
        fields = ("issue_type", "comment", "corrected_data")
        extra_kwargs = {
            "comment": {"required": False},
            "corrected_data": {"required": False},
        }


class InferenceFeedbackSerializer(serializers.ModelSerializer):
    class Meta:
        model = InferenceFeedback
        fields = (
            "id",
            "job",
            "user",
            "issue_type",
            "comment",
            "corrected_data",
            "status",
            "created_at",
            "reviewed_at",
        )
        read_only_fields = ("id", "job", "user", "created_at", "reviewed_at")


class InferenceFeedbackReviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = InferenceFeedback
        fields = ("status",)
