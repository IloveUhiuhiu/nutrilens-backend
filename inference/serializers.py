from rest_framework import serializers
from .models import InferenceFeedback, InferenceJob, InferenceResult


class InferenceJobCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = InferenceJob
        fields = ("image", "model_version")
        extra_kwargs = {"model_version": {"required": False}}


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
    result = InferenceResultSerializer(read_only=True)

    class Meta:
        model = InferenceJob
        fields = (
            "id",
            "image",
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
