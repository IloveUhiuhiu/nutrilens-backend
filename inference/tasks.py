from datetime import timedelta

from celery import shared_task
from django.db import transaction
from django.utils import timezone

from .cloudinary_upload import CloudinaryUploadError, upload_image_to_cloudinary
from .models import InferenceJob, InferenceResult
from .services import TransientAIError, call_ai_analysis_server, normalize_ai_result


# Single source of truth for the retry budget, shared between the decorator
# (which actually drives Celery's autoretry) and the in-task check below
# (which needs to know, before Celery decides, whether *this* failure will
# still be retried — so it can avoid marking the job "failed" prematurely).
MAX_RETRIES = 2

# A job stuck in "running" longer than this is treated as abandoned (worker
# crashed) and may be reclaimed. Must exceed the worst-case AI latency
# (AI_SERVER_TIMEOUT × retries + backoff) — with AI_SERVER_TIMEOUT=60s and
# max_retries=2, that's up to 3×60s of request time plus 2 backoffs of a
# few seconds each ≈ 3 minutes, so this needs real headroom above that, not
# just equal to it.
STALE_RUNNING_AFTER = timedelta(minutes=10)


@shared_task(
    bind=True,
    acks_late=True,
    # Only transient failures are retried; permanent ones (4xx / invalid
    # payload) fail fast instead of re-running the expensive AI pipeline.
    autoretry_for=(TransientAIError,),
    retry_backoff=True,
    retry_backoff_max=60,
    retry_jitter=True,
    retry_kwargs={"max_retries": MAX_RETRIES},
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
            #
            # Deliberately does NOT also match "retrying": that status means
            # the previous attempt has already finished (transiently failed)
            # and nothing is in-flight right now — this task's own Celery
            # autoretry scheduled this exact re-run, so it's safe (and
            # required) to fall through and actually call the AI server again.
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
        except Exception as exc:
            # Anything other than CloudinaryUploadError (e.g. the image file
            # isn't visible on this worker's filesystem) must still mark the
            # job failed — otherwise it's stuck at "running" forever with no
            # error recorded, and the AI server is never called.
            job.status = "failed"
            job.error_message = f"Could not read or upload job image: {exc}"
            job.save(update_fields=["status", "error_message", "updated_at"])
            return job.id

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
        # A TransientAIError with retry budget left is about to be retried by
        # Celery's autoretry (raised below) — keep the job at "retrying"
        # rather than "failed" so a polling client doesn't mistake this for
        # the final outcome. Anything else (PermanentAIError, or a
        # TransientAIError on the last allowed attempt, or an unrelated bug)
        # really is final: no more retries are coming.
        will_retry = (
            isinstance(exc, TransientAIError) and self.request.retries < MAX_RETRIES
        )
        job.status = "retrying" if will_retry else "failed"
        job.error_message = getattr(exc, "public_message", str(exc))
        error_detail = getattr(exc, "detail", "")
        if error_detail:
            job.error_message = f"{job.error_message} Detail: {error_detail}"
        # ai_error_code (vd. no_food_detected, depth_estimation_failed...) cho phép
        # mobile/FE hiển thị thông báo cụ thể theo loại lỗi thay vì chỉ error_message
        # dạng text tự do. Lỗi không đến từ AI server (vd. lỗi code ở task này) sẽ
        # không có ai_error_code -> lưu rỗng, mobile dùng error_message/fallback chung.
        job.error_code = getattr(exc, "ai_error_code", "") or ""
        job.save(update_fields=["status", "error_message", "error_code", "updated_at"])
        raise

    return job.id
