from django.db.models import Avg, Count, Q
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, OpenApiTypes, extend_schema
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser, IsAuthenticated

from core.api import DEFAULT_ERROR_RESPONSES, api_response, handle_api_exceptions, not_found_response, paginate_queryset, validation_error_response
from .cloudinary_upload import CloudinaryUploadError, upload_image_to_cloudinary
from .models import InferenceFeedback, InferenceJob, InferenceResult
from .serializers import (
    InferenceFeedbackCreateSerializer,
    InferenceFeedbackReviewSerializer,
    InferenceFeedbackSerializer,
    InferenceJobCreateSerializer,
    InferenceJobSerializer,
    InferenceResultSerializer,
)
from .tasks import process_inference_job_task


@extend_schema(summary="Tạo job phân tích ảnh", request=InferenceJobCreateSerializer, responses={201: OpenApiTypes.OBJECT, **DEFAULT_ERROR_RESPONSES})
@api_view(["POST"])
@permission_classes([IsAuthenticated])
@handle_api_exceptions
def image_inference(request):
    """Chức năng: API tạo job phân tích ảnh. Đầu vào: image multipart hoặc URL và camera_metadata. Đầu ra: InferenceJob pending."""
    serializer = InferenceJobCreateSerializer(data=request.data)
    if not serializer.is_valid():
        return validation_error_response(serializer)
    job = serializer.save(user=request.user, status="pending")
    if job.image and not job.image_url:
        try:
            with job.image.open("rb") as image_file:
                job.image_url = upload_image_to_cloudinary(
                    image_file,
                    public_id=f"{job.id}/original",
                )
            job.save(update_fields=["image_url", "updated_at"])
        except CloudinaryUploadError as exc:
            job.status = "failed"
            job.error_message = exc.public_message
            if exc.detail:
                job.error_message = f"{job.error_message} Detail: {exc.detail}"
            job.save(update_fields=["status", "error_message", "updated_at"])
            return api_response(
                exc.public_message,
                status_code=exc.status_code,
                errors={"cloudinary": [exc.detail or exc.public_message]},
            )
    try:
        process_inference_job_task.delay(job.id)
    except Exception as exc:
        job.status = "failed"
        job.error_message = f"Could not enqueue inference task: {exc}"
        job.save(update_fields=["status", "error_message", "updated_at"])
        return api_response(
            "Could not enqueue inference task.",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            errors={"task_queue": [str(exc)]},
        )
    return api_response("Inference job created successfully.", status_code=status.HTTP_201_CREATED, data=InferenceJobSerializer(job).data)


@extend_schema(summary="Chi tiết job phân tích", responses={200: OpenApiTypes.OBJECT, **DEFAULT_ERROR_RESPONSES})
@api_view(["GET"])
@permission_classes([IsAuthenticated])
@handle_api_exceptions
def job_detail(request, id):
    """Chức năng: API xem trạng thái job. Đầu vào: job id. Đầu ra: InferenceJob hoặc lỗi 404."""
    job = InferenceJob.objects.filter(id=id, user=request.user).first()
    if not job:
        return not_found_response("Inference job not found.")
    return api_response("Inference job retrieved successfully.", data=InferenceJobSerializer(job).data)


@extend_schema(summary="Kết quả job phân tích", responses={200: OpenApiTypes.OBJECT, **DEFAULT_ERROR_RESPONSES})
@api_view(["GET"])
@permission_classes([IsAuthenticated])
@handle_api_exceptions
def job_result(request, id):
    """Chức năng: API lấy kết quả AI. Đầu vào: job id. Đầu ra: InferenceResult hoặc lỗi 404."""
    job = InferenceJob.objects.filter(id=id, user=request.user).first()
    if not job:
        return not_found_response("Inference job not found.")
    if job.status == "failed":
        return api_response(
            "Inference job failed.",
            status_code=status.HTTP_502_BAD_GATEWAY,
            errors={"inference": [job.error_message or "Inference job failed."]},
        )
    result = InferenceResult.objects.filter(job=job).first()
    if not result:
        return not_found_response("Inference result not found.")
    return api_response("Inference result retrieved successfully.", data=InferenceResultSerializer(result).data)


@extend_schema(summary="Gửi feedback kết quả AI", request=InferenceFeedbackCreateSerializer, responses={201: OpenApiTypes.OBJECT, **DEFAULT_ERROR_RESPONSES})
@api_view(["POST"])
@permission_classes([IsAuthenticated])
@handle_api_exceptions
def job_feedback(request, id):
    """Chức năng: API gửi feedback kết quả AI. Đầu vào: job id và payload feedback. Đầu ra: InferenceFeedback."""
    job = InferenceJob.objects.filter(id=id, user=request.user).first()
    if not job:
        return not_found_response("Inference job not found.")
    serializer = InferenceFeedbackCreateSerializer(data=request.data)
    if not serializer.is_valid():
        return validation_error_response(serializer)
    feedback = serializer.save(job=job, user=request.user)
    return api_response("Inference feedback created successfully.", status_code=status.HTTP_201_CREATED, data=InferenceFeedbackSerializer(feedback).data)


@extend_schema(summary="Admin danh sách job AI", parameters=[OpenApiParameter("status", OpenApiTypes.STR), OpenApiParameter("search", OpenApiTypes.STR)], responses={200: OpenApiTypes.OBJECT, **DEFAULT_ERROR_RESPONSES})
@api_view(["GET"])
@permission_classes([IsAdminUser])
@handle_api_exceptions
def admin_job_list(request):
    """Chức năng: API admin danh sách job AI. Đầu vào: status/search/page. Đầu ra: danh sách InferenceJob."""
    queryset = InferenceJob.objects.all().select_related("user").order_by("-created_at")
    job_status = request.query_params.get("status")
    search = request.query_params.get("search")
    if job_status:
        queryset = queryset.filter(status=job_status)
    if search:
        queryset = queryset.filter(Q(id__icontains=search) | Q(user__email__icontains=search))
    return api_response("Inference jobs retrieved successfully.", data=paginate_queryset(request, queryset, InferenceJobSerializer))


@extend_schema(summary="Admin chi tiết job AI", responses={200: OpenApiTypes.OBJECT, **DEFAULT_ERROR_RESPONSES})
@api_view(["GET"])
@permission_classes([IsAdminUser])
@handle_api_exceptions
def admin_job_detail(request, id):
    """Chức năng: API admin chi tiết job AI. Đầu vào: job id. Đầu ra: InferenceJob hoặc lỗi 404."""
    job = InferenceJob.objects.filter(id=id).first()
    if not job:
        return not_found_response("Inference job not found.")
    return api_response("Inference job retrieved successfully.", data=InferenceJobSerializer(job).data)


@extend_schema(summary="Admin metrics inference", responses={200: OpenApiTypes.OBJECT, **DEFAULT_ERROR_RESPONSES})
@api_view(["GET"])
@permission_classes([IsAdminUser])
@handle_api_exceptions
def admin_metrics(request):
    """Chức năng: API admin metrics inference. Đầu vào: request admin. Đầu ra: tổng job, trạng thái, latency, feedback."""
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


@extend_schema(summary="Admin danh sách feedback AI", responses={200: OpenApiTypes.OBJECT, **DEFAULT_ERROR_RESPONSES})
@api_view(["GET"])
@permission_classes([IsAdminUser])
@handle_api_exceptions
def admin_feedback_list(request):
    """Chức năng: API admin danh sách feedback AI. Đầu vào: page. Đầu ra: danh sách InferenceFeedback."""
    queryset = InferenceFeedback.objects.all().select_related("job", "user").order_by("-created_at")
    return api_response("Inference feedback retrieved successfully.", data=paginate_queryset(request, queryset, InferenceFeedbackSerializer))


@extend_schema(summary="Admin cập nhật feedback AI", request=InferenceFeedbackReviewSerializer, responses={200: OpenApiTypes.OBJECT, **DEFAULT_ERROR_RESPONSES})
@api_view(["PATCH"])
@permission_classes([IsAdminUser])
@handle_api_exceptions
def admin_feedback_review(request, id):
    """Chức năng: API admin cập nhật feedback AI. Đầu vào: feedback id và status. Đầu ra: InferenceFeedback."""
    feedback = InferenceFeedback.objects.filter(id=id).first()
    if not feedback:
        return not_found_response("Inference feedback not found.")
    serializer = InferenceFeedbackReviewSerializer(feedback, data=request.data, partial=True)
    if not serializer.is_valid():
        return validation_error_response(serializer)
    feedback = serializer.save(reviewed_at=timezone.now())
    return api_response("Inference feedback updated successfully.", data=InferenceFeedbackSerializer(feedback).data)
