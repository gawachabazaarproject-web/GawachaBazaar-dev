"""Image upload via Cloudinary - the one place in this backend that ever
accepts a raw uploaded file. Every field that stores an image (Product's
image_url rows, Category's new image_url column) still only ever stores
a plain URL string exactly as it already did when an admin pasted one by
hand - this module is strictly additive infrastructure sitting in front
of those same fields, not a change to how they're used downstream.

CLOUDINARY_* being unset is treated as "not configured", failing with a
clear 503 rather than silently no-op-ing or fabricating a fake URL - the
same honest-placeholder precedent as PaymentGateway/NotificationGateway
elsewhere in this codebase for a capability that depends on a
third-party account this repo doesn't control.
"""

from typing import Any

import cloudinary
import cloudinary.uploader
from fastapi import UploadFile

from app.core.config import settings
from app.exceptions.base import AppException, BusinessValidationError

MAX_UPLOAD_BYTES = 8 * 1024 * 1024  # 8 MB
_ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}

_configured = False


def _ensure_configured() -> None:
    global _configured
    if _configured:
        return
    if not (
        settings.CLOUDINARY_CLOUD_NAME
        and settings.CLOUDINARY_API_KEY
        and settings.CLOUDINARY_API_SECRET
    ):
        raise AppException(
            "Image uploads are not configured on this server (missing Cloudinary credentials).",
            status_code=503,
            code="UPLOADS_NOT_CONFIGURED",
        )
    cloudinary.config(
        cloud_name=settings.CLOUDINARY_CLOUD_NAME,
        api_key=settings.CLOUDINARY_API_KEY,
        api_secret=settings.CLOUDINARY_API_SECRET,
        secure=True,
    )
    _configured = True


def upload_image(file: UploadFile, *, folder: str) -> dict[str, Any]:
    """Validates and uploads one image file to Cloudinary under `folder`
    (a fixed, server-chosen string per call site - never client-supplied,
    so there's no path-traversal-style concern about what folder a
    caller can write into). Returns Cloudinary's `secure_url`/`public_id`.

    Every route in this codebase is sync `def` except the one place that
    genuinely needs async (the payment webhook, for its exact-raw-body
    requirement - see api/v1/payments.py). This follows the same rule:
    `UploadFile.file` is the underlying SpooledTemporaryFile, readable
    synchronously, so this stays a plain sync call from a sync route.
    """
    _ensure_configured()

    if file.content_type not in _ALLOWED_CONTENT_TYPES:
        raise BusinessValidationError(
            f"Unsupported image type: {file.content_type or 'unknown'}. "
            "Allowed: JPEG, PNG, WEBP, GIF."
        )

    file.file.seek(0, 2)  # seek to end
    size = file.file.tell()
    file.file.seek(0)
    if size > MAX_UPLOAD_BYTES:
        raise BusinessValidationError(
            f"Image is too large ({size / 1_048_576:.1f} MB) - the limit is "
            f"{MAX_UPLOAD_BYTES / 1_048_576:.0f} MB."
        )
    if size == 0:
        raise BusinessValidationError("The uploaded file is empty.")

    result = cloudinary.uploader.upload(
        file.file,
        folder=folder,
        resource_type="image",
    )
    return {"secure_url": result["secure_url"], "public_id": result["public_id"]}
