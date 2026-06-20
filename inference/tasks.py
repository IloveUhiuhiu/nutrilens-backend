from datetime import timedelta

from celery import shared_task
from django.db import transaction
from django.utils import timezone

from .cloudinary_upload import CloudinaryUploadError, upload_image_to_cloudinary
from .models import InferenceJob, InferenceResult
from .services import TransientAIError, call_ai_analysis_server, normalize_ai_result


# A job stuck in "running" longer than this is treated as abandoned (worker
# crashed) and may be reclaimed. Must exceed the worst-case AI latency
# (AI_SERVER_TIMEOUT × retries + backoff).
STALE_RUNNING_AFTER = timedelta(minutes=5)


@shared_task(
    bind=True,
    acks_late=True,
    # Only transient failures are retried; permanent ones (4xx / invalid
    # payload) fail fast instead of re-running the expensive AI pipeline.
    autoretry_for=(TransientAIError,),
    retry_backoff=True,
    retry_backoff_max=60,
    retry_jitter=True,
    retry_kwargs={"max_retries": 2},
)
def process_inference_job_task(self, job_id):
    """Chức năng: xử lý job AI bất đồng bộ, idempotent. Đầu vào: job_id. Đầu ra: job_id sau khi lưu kết quả."""
    # Claim the job atomically so a duplicate enqueue or an overlapping retry
    # cannot run the AI pipeline twice for the same job.
    with transaction.atomic():
        job = (
            InferenceJob.objects.select_for_update(skip_locked=True)
            .filter(id=job_id)
            .first()
        )
        if job is None:
            # Either the job vanished or another worker holds the row lock and
            # is already processing it — nothing to do here.
            return job_id
        if job.status == "succeeded":
            return job.id
        if (
            job.status == "running"
            and timezone.now() - job.updated_at < STALE_RUNNING_AFTER
        ):
            # Actively processed by another worker; skip to avoid a duplicate
            # AI request. Stale "running" jobs fall through and are reclaimed.
            return job.id
        job.status = "running"
        job.error_message = ""
        job.save(update_fields=["status", "error_message", "updated_at"])

    # Upload the original image to Cloudinary here (off the request path). The
    # public_id is deterministic per job, so a redelivery overwrites the same
    # asset rather than creating a duplicate.
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
            return job.id  # permanent for this job; not retried

    try:
        payload = call_ai_analysis_server(job)
        normalized = normalize_ai_result(payload)
        InferenceResult.objects.update_or_create(
            job=job,
            defaults={
                "total_calories": normalized["total_calories"],
                "total_protein": normalized["total_protein"],
                "total_carbs": normalized["total_carbs"],
                "total_fat": normalized["total_fat"],
                "total_weight": normalized["total_weight"],
                "components": normalized["components"],
            },
        )
        job.status = "succeeded"
        job.raw_output = payload
        job.latency_ms = normalized["latency_ms"]
        if normalized["model_version"]:
            job.model_version = normalized["model_version"]
        job.save(update_fields=["status", "raw_output", "latency_ms", "model_version", "updated_at"])
    except Exception as exc:
        job.status = "failed"
        job.error_message = getattr(exc, "public_message", str(exc))
        error_detail = getattr(exc, "detail", "")
        if error_detail:
            job.error_message = f"{job.error_message} Detail: {error_detail}"
        job.save(update_fields=["status", "error_message", "updated_at"])
        raise

    return job.id
