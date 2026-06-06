import hashlib
import time

import requests
from django.conf import settings
from rest_framework import status


class CloudinaryUploadError(Exception):
    """Lỗi upload ảnh lên Cloudinary."""

    def __init__(self, message, status_code=status.HTTP_502_BAD_GATEWAY, detail=""):
        self.public_message = message
        self.status_code = status_code
        self.detail = detail
        super().__init__(message)


def upload_image_to_cloudinary(uploaded_file, public_id=None):
    """Upload file ảnh từ request lên Cloudinary và trả secure_url."""
    if not settings.CLOUDINARY_CLOUD_NAME:
        raise CloudinaryUploadError(
            "CLOUDINARY_CLOUD_NAME is not configured.",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    params = {
        "folder": settings.CLOUDINARY_FOLDER,
    }
    if public_id:
        params["public_id"] = public_id

    if settings.CLOUDINARY_UPLOAD_PRESET:
        params["upload_preset"] = settings.CLOUDINARY_UPLOAD_PRESET

    if settings.CLOUDINARY_API_KEY and settings.CLOUDINARY_API_SECRET:
        params["api_key"] = settings.CLOUDINARY_API_KEY
        params["timestamp"] = int(time.time())
        params["signature"] = _sign_params(params, settings.CLOUDINARY_API_SECRET)
    elif not settings.CLOUDINARY_UPLOAD_PRESET:
        raise CloudinaryUploadError(
            "Cloudinary upload requires either signed credentials or an unsigned upload preset.",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    upload_url = (
        f"https://api.cloudinary.com/v1_1/"
        f"{settings.CLOUDINARY_CLOUD_NAME}/image/upload"
    )
    content_type = getattr(uploaded_file, "content_type", None) or "image/jpeg"
    file_name = getattr(uploaded_file, "name", "image.jpg")

    try:
        response = requests.post(
            upload_url,
            data=params,
            files={"file": (file_name, uploaded_file, content_type)},
            timeout=settings.CLOUDINARY_UPLOAD_TIMEOUT,
        )
        response.raise_for_status()
        payload = response.json()
    except requests.Timeout as exc:
        raise CloudinaryUploadError(
            "Cloudinary upload timed out.",
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
        ) from exc
    except requests.HTTPError as exc:
        detail = exc.response.text[:1000] if exc.response is not None else ""
        raise CloudinaryUploadError(
            "Cloudinary upload failed.",
            detail=detail,
        ) from exc
    except (requests.RequestException, ValueError) as exc:
        raise CloudinaryUploadError("Cloudinary upload failed.") from exc

    secure_url = payload.get("secure_url") or payload.get("url")
    if not secure_url:
        raise CloudinaryUploadError(
            "Cloudinary response did not include secure_url.",
            detail=str(payload)[:1000],
        )
    return secure_url


def _sign_params(params, api_secret):
    signed = {
        key: value
        for key, value in params.items()
        if key not in {"file", "api_key", "signature"} and value not in ("", None)
    }
    raw = "&".join(f"{key}={signed[key]}" for key in sorted(signed))
    return hashlib.sha1(f"{raw}{api_secret}".encode("utf-8")).hexdigest()
