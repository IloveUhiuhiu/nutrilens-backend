from celery import shared_task

from .models import InferenceJob, InferenceResult
from .services import call_ai_analysis_server, normalize_ai_result


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={"max_retries": 2})
def process_inference_job_task(self, job_id):
    """Chức năng: xử lý job AI bất đồng bộ. Đầu vào: job_id. Đầu ra: job_id sau khi lưu kết quả."""
    job = InferenceJob.objects.get(id=job_id)
    job.status = "running"
    job.error_message = ""
    job.save(update_fields=["status", "error_message", "updated_at"])

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
