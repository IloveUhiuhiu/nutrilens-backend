from django.db.models import Avg, Count, Q
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, OpenApiTypes, extend_schema
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser, IsAuthenticated

from core.api import DEFAULT_ERROR_RESPONSES, api_response, handle_api_exceptions, not_found_response, paginate_queryset, validation_error_response
from .models import InferenceFeedback, InferenceJob, InferenceResult
from .serializers import (
    InferenceFeedbackCreateSerializer,
    InferenceFeedbackReviewSerializer,
    InferenceFeedbackSerializer,
    InferenceJobCreateSerializer,
    InferenceJobSerializer,
    InferenceResultSerializer,
)


@extend_schema(request=InferenceJobCreateSerializer, responses={201: OpenApiTypes.OBJECT, **DEFAULT_ERROR_RESPONSES})
@api_view(["POST"])
@permission_classes([IsAuthenticated])
@handle_api_exceptions
def image_inference(request):
    serializer = InferenceJobCreateSerializer(data=request.data)
    if not serializer.is_valid():
        return validation_error_response(serializer)
    job = serializer.save(user=request.user, status="pending")
    return api_response("Inference job created successfully.", status_code=status.HTTP_201_CREATED, data=InferenceJobSerializer(job).data)


@extend_schema(responses={200: OpenApiTypes.OBJECT, **DEFAULT_ERROR_RESPONSES})
@api_view(["GET"])
@permission_classes([IsAuthenticated])
@handle_api_exceptions
def job_detail(request, id):
    job = InferenceJob.objects.filter(id=id, user=request.user).first()
    if not job:
        return not_found_response("Inference job not found.")
    return api_response("Inference job retrieved successfully.", data=InferenceJobSerializer(job).data)


@extend_schema(responses={200: OpenApiTypes.OBJECT, **DEFAULT_ERROR_RESPONSES})
@api_view(["GET"])
@permission_classes([IsAuthenticated])
@handle_api_exceptions
def job_result(request, id):
    job = InferenceJob.objects.filter(id=id, user=request.user).first()
    if not job:
        return not_found_response("Inference job not found.")
    result = InferenceResult.objects.filter(job=job).first()
    if not result:
        return not_found_response("Inference result not found.")
    return api_response("Inference result retrieved successfully.", data=InferenceResultSerializer(result).data)


@extend_schema(request=InferenceFeedbackCreateSerializer, responses={201: OpenApiTypes.OBJECT, **DEFAULT_ERROR_RESPONSES})
@api_view(["POST"])
@permission_classes([IsAuthenticated])
@handle_api_exceptions
def job_feedback(request, id):
    job = InferenceJob.objects.filter(id=id, user=request.user).first()
    if not job:
        return not_found_response("Inference job not found.")
    serializer = InferenceFeedbackCreateSerializer(data=request.data)
    if not serializer.is_valid():
        return validation_error_response(serializer)
    feedback = serializer.save(job=job, user=request.user)
    return api_response("Inference feedback created successfully.", status_code=status.HTTP_201_CREATED, data=InferenceFeedbackSerializer(feedback).data)


@extend_schema(parameters=[OpenApiParameter("status", OpenApiTypes.STR), OpenApiParameter("search", OpenApiTypes.STR)], responses={200: OpenApiTypes.OBJECT, **DEFAULT_ERROR_RESPONSES})
@api_view(["GET"])
@permission_classes([IsAdminUser])
@handle_api_exceptions
def admin_job_list(request):
    queryset = InferenceJob.objects.all().select_related("user").order_by("-created_at")
    job_status = request.query_params.get("status")
    search = request.query_params.get("search")
    if job_status:
        queryset = queryset.filter(status=job_status)
    if search:
        queryset = queryset.filter(Q(id__icontains=search) | Q(user__email__icontains=search))
    return api_response("Inference jobs retrieved successfully.", data=paginate_queryset(request, queryset, InferenceJobSerializer))


@extend_schema(responses={200: OpenApiTypes.OBJECT, **DEFAULT_ERROR_RESPONSES})
@api_view(["GET"])
@permission_classes([IsAdminUser])
@handle_api_exceptions
def admin_job_detail(request, id):
    job = InferenceJob.objects.filter(id=id).first()
    if not job:
        return not_found_response("Inference job not found.")
    return api_response("Inference job retrieved successfully.", data=InferenceJobSerializer(job).data)


@extend_schema(responses={200: OpenApiTypes.OBJECT, **DEFAULT_ERROR_RESPONSES})
@api_view(["GET"])
@permission_classes([IsAdminUser])
@handle_api_exceptions
def admin_metrics(request):
    total = InferenceJob.objects.count()
    by_status = dict(InferenceJob.objects.values_list("status").annotate(count=Count("id")))
    avg_latency = InferenceJob.objects.filter(latency_ms__gt=0).aggregate(value=Avg("latency_ms"))["value"] or 0
    return api_response(
        "Inference metrics retrieved successfully.",
        data={
            "total_jobs": total,
            "by_status": by_status,
            "average_latency_ms": round(avg_latency, 2),
            "feedback_open": InferenceFeedback.objects.filter(status="open").count(),
        },
    )


@extend_schema(responses={200: OpenApiTypes.OBJECT, **DEFAULT_ERROR_RESPONSES})
@api_view(["GET"])
@permission_classes([IsAdminUser])
@handle_api_exceptions
def admin_feedback_list(request):
    queryset = InferenceFeedback.objects.all().select_related("job", "user").order_by("-created_at")
    return api_response("Inference feedback retrieved successfully.", data=paginate_queryset(request, queryset, InferenceFeedbackSerializer))


@extend_schema(request=InferenceFeedbackReviewSerializer, responses={200: OpenApiTypes.OBJECT, **DEFAULT_ERROR_RESPONSES})
@api_view(["PATCH"])
@permission_classes([IsAdminUser])
@handle_api_exceptions
def admin_feedback_review(request, id):
    feedback = InferenceFeedback.objects.filter(id=id).first()
    if not feedback:
        return not_found_response("Inference feedback not found.")
    serializer = InferenceFeedbackReviewSerializer(feedback, data=request.data, partial=True)
    if not serializer.is_valid():
        return validation_error_response(serializer)
    feedback = serializer.save(reviewed_at=timezone.now())
    return api_response("Inference feedback updated successfully.", data=InferenceFeedbackSerializer(feedback).data)
