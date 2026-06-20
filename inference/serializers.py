import json
from urllib.parse import urlsplit

from PIL import Image
from rest_framework import serializers
from .models import InferenceFeedback, InferenceJob, InferenceResult


MAX_UPLOAD_IMAGE_SIZE = 10 * 1024 * 1024  # 10 MB


class ImageOrUrlField(serializers.Field):
    def to_internal_value(self, value):
        if hasattr(value, "read"):
            content_type = getattr(value, "content_type", "")
            if content_type and not content_type.startswith("image/"):
                raise serializers.ValidationError("Uploaded file must be an image.")
            size = getattr(value, "size", None)
            if size is not None and size > MAX_UPLOAD_IMAGE_SIZE:
                raise serializers.ValidationError("Uploaded image is too large (max 10MB).")
            # Verify the bytes are a real, decodable image — defends against a
            # spoofed content-type header on a non-image payload.
            try:
                value.seek(0)
                Image.open(value).verify()
            except Exception as exc:
                raise serializers.ValidationError("Uploaded file is not a valid image.") from exc
            finally:
                try:
                    value.seek(0)
                except (AttributeError, OSError):
                    pass
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
    # Optional dense depth map (ARCore Depth API / ARKit sceneDepth on devices
    # that actually have it — ToF/LiDAR or motion-stereo). depth_metadata
    # carries how to decode it (depth_unit, file_extension); both are absent
    # for devices/captures with no depth map, which fall back to AI-estimated
    # depth on the server.
    depth_map = serializers.FileField(write_only=True, required=False, allow_null=True)
    depth_metadata = serializers.JSONField(required=False)

    class Meta:
        model = InferenceJob
        fields = ("image", "camera_metadata", "depth_map", "depth_metadata")

    def validate_depth_metadata(self, value):
        """Chức năng: parse depth_metadata multipart (JSON string hoặc dict). Đầu vào: value. Đầu ra: dict."""
        return self._parse_json_object(value, "depth_metadata")

    def validate_camera_metadata(self, value):
        """Chức năng: kiểm tra metadata camera. Đầu vào: dict hoặc JSON string. Đầu ra: dict hợp lệ."""
        metadata = self._parse_json_object(value, "camera_metadata")
        metadata = self._normalize_mobile_camera_metadata(metadata)
        if "distance_cm" in metadata and "camera_height_cm" not in metadata and "camera_height_mm" not in metadata:
            metadata["camera_height_cm"] = metadata["distance_cm"]
        has_physical_camera_height = "camera_height_cm" in metadata or "camera_height_mm" in metadata
        has_pixel_area = "pixel_area_cm2" in metadata or "camera_area" in metadata
        has_intrinsics = self._has_camera_intrinsics(metadata)
        if not has_physical_camera_height and not has_intrinsics:
            raise serializers.ValidationError("camera_height_cm/camera_height_mm or camera intrinsics fx/fy is required.")
        if not has_pixel_area and not has_intrinsics:
            raise serializers.ValidationError("pixel_area_cm2 or camera intrinsics fx/fy is required.")
        return metadata

    def _normalize_mobile_camera_metadata(self, metadata):
        """Chức năng: bổ sung alias metadata ảnh mobile. Đầu vào: metadata. Đầu ra: metadata đã chuẩn hóa."""
        width = self._number_value(metadata.get("camera_width") or metadata.get("width"))
        height = self._number_value(metadata.get("camera_height") or metadata.get("height"))

        if width is not None:
            metadata.setdefault("camera_width", width)
        if height is not None:
            metadata.setdefault("camera_height", height)
        if width is not None and height is not None:
            metadata.setdefault("camera_area", width * height)

        if "intrinsics" not in metadata and "fx" in metadata and "fy" in metadata:
            metadata["intrinsics"] = {
                "fx": metadata.get("fx"),
                "fy": metadata.get("fy"),
                "cx": metadata.get("cx"),
                "cy": metadata.get("cy"),
            }

        # AR captures (ARCore/ARKit) provide an absolute camera-to-food distance
        # in cm; feed it into the distance/height fields the volume estimator
        # expects so absolute depth is actually used.
        distance = self._number_value(metadata.get("camera_to_object_distance"))
        if distance is not None and metadata.get("has_absolute_depth"):
            metadata.setdefault("distance_cm", distance)
            metadata.setdefault("camera_height_cm", distance)

        return metadata

    def _has_camera_intrinsics(self, metadata):
        """Chức năng: kiểm tra intrinsics ở root hoặc nested. Đầu vào: metadata. Đầu ra: bool."""
        intrinsics = metadata.get("intrinsics") or {}
        return ("fx" in metadata and "fy" in metadata) or ("fx" in intrinsics and "fy" in intrinsics)

    def _number_value(self, value):
        """Chức năng: ép số metadata. Đầu vào: value bất kỳ. Đầu ra: int/float hoặc None."""
        if value in (None, ""):
            return None
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        return int(number) if number.is_integer() else number

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
    components = serializers.SerializerMethodField()

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

    def get_components(self, obj):
        from nutrients.models import IngredientPhysicalData
        enriched = []
        physical_data_cache = {}
        ids = [c.get("physical_data_id") for c in (obj.components or []) if c.get("physical_data_id")]
        if ids:
            qs = IngredientPhysicalData.objects.filter(id__in=ids).only("id", "vi_name", "image_url")
            physical_data_cache = {pd.id: pd for pd in qs}
        for comp in (obj.components or []):
            comp_copy = dict(comp)
            pd = physical_data_cache.get(comp_copy.get("physical_data_id"))
            if pd:
                comp_copy.setdefault("physical_data_name", pd.vi_name)
                if not comp_copy.get("image_url") and pd.image_url:
                    comp_copy["image_url"] = pd.image_url
            enriched.append(comp_copy)
        return enriched


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


FEEDBACK_ISSUE_TYPE_CHOICES = [
    "wrong_component",
    "wrong_portion",
    "wrong_food_region",
]


class InferenceFeedbackCreateSerializer(serializers.Serializer):
    """Chức năng: nhận feedback đa loại lỗi từ mobile. Đầu vào: issue_types, actual_components, notes. Đầu ra: InferenceFeedback."""

    issue_types = serializers.ListField(
        child=serializers.ChoiceField(choices=FEEDBACK_ISSUE_TYPE_CHOICES),
        min_length=1,
    )
    actual_components = serializers.ListField(
        child=serializers.CharField(max_length=150, allow_blank=True),
        required=False,
        default=list,
    )
    notes = serializers.CharField(required=False, allow_blank=True, default="")

    def create(self, validated_data):
        return InferenceFeedback.objects.create(
            job=validated_data["job"],
            user=validated_data["user"],
            issue_type=",".join(validated_data["issue_types"]),
            comment=validated_data.get("notes", ""),
            corrected_data={"actual_components": validated_data.get("actual_components", [])},
        )


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
