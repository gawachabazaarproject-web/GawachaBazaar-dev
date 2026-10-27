"""Image upload via Cloudinary - the one place in this backend that ever
accepts a raw uploaded file. Every field that stores an image (Product's
image_url rows, Category's new image_url column) still only ever stores
a plain URL string exactly as it already did when an admin pasted one by
hand - this module is strictly additive infrastructure sitting in front
of those same fields, not a change to how they're used downstream.

CLOUDINARY_* being unset is treated as "not configured", failing with a
clear 503 rather than silently no-op-ing or fabricating a fake URL - the
same honest-placeholder precedent as PaymentGateway elsewhere in this codebase for a capability that depends on a
third-party account this repo doesn't control.

Hardening (DEL-15): the uploaded BYTES are validated (signature, full decode,
dimensions, declared type must match), the client file name is never used, and
`release_image` removes our own replaced/deleted assets from Cloudinary.
"""

import io
import re
from dataclasses import dataclass
from typing import Any

import cloudinary
import cloudinary.exceptions
import cloudinary.uploader
from fastapi import UploadFile
from PIL import Image, UnidentifiedImageError

from app.core.config import settings
from app.core.logging import logger
from app.exceptions.base import AppException, BusinessValidationError

MAX_UPLOAD_BYTES = 8 * 1024 * 1024  # 8 MB
_ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
# Pillow format name -> the content type it must have been declared as.
_FORMAT_TO_MIME = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp", "GIF": "image/gif"}
MIN_SIDE_PX = 16
MAX_SIDE_PX = 8000
MAX_PIXELS = 40_000_000  # blocks "decompression bomb" files that are tiny on disk

_configured = False


@dataclass(frozen=True)
class ImageInfo:
    format: str
    width: int
    height: int


def validate_image_bytes(data: bytes, declared_content_type: str | None) -> ImageInfo:
    """The client's Content-Type is only a hint. The bytes decide: the file
    signature must be JPEG/PNG/WEBP/GIF, the file must fully decode, the
    dimensions must be sane (size is read from the header BEFORE decoding so a
    small file declaring a gigantic canvas is refused without allocating it),
    and the detected format must agree with the declared type."""
    if not data:
        raise BusinessValidationError("The uploaded file is empty.")
    if len(data) > MAX_UPLOAD_BYTES:
        raise BusinessValidationError(
            f"Image is too large - the limit is {MAX_UPLOAD_BYTES / 1_048_576:.0f} MB."
        )
    try:
        with Image.open(io.BytesIO(data)) as probe:
            fmt = probe.format
            width, height = probe.size  # header only, nothing decoded yet
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as exc:
        raise BusinessValidationError("The file is not a valid image.") from exc
    if fmt not in _FORMAT_TO_MIME:
        raise BusinessValidationError("Unsupported image format. Allowed: JPEG, PNG, WEBP, GIF.")
    if declared_content_type != _FORMAT_TO_MIME[fmt]:
        raise BusinessValidationError(
            f"The file content is {fmt} but it was declared as {declared_content_type or 'unknown'}."
        )
    if min(width, height) < MIN_SIDE_PX or max(width, height) > MAX_SIDE_PX or width * height > MAX_PIXELS:
        raise BusinessValidationError(
            f"Image dimensions {width}x{height} are not allowed "
            f"(each side {MIN_SIDE_PX}-{MAX_SIDE_PX}px, at most {MAX_PIXELS // 1_000_000} megapixels)."
        )
    try:  # full decode: catches truncated / corrupt / polyglot payloads
        with Image.open(io.BytesIO(data)) as img:
            img.load()
    except (OSError, ValueError, SyntaxError, Image.DecompressionBombError) as exc:
        raise BusinessValidationError("The image is corrupt or incomplete.") from exc
    return ImageInfo(fmt, width, height)


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
    # A value pasted into a dashboard with a stray space or newline fails
    # as "Invalid Signature", which is hard to spot by eye.
    cloudinary.config(
        cloud_name=settings.CLOUDINARY_CLOUD_NAME.strip(),
        api_key=settings.CLOUDINARY_API_KEY.strip(),
        api_secret=settings.CLOUDINARY_API_SECRET.strip(),
        secure=True,
    )
    _configured = True


def upload_image(file: UploadFile, *, folder: str) -> dict[str, Any]:
    """Validates and uploads one image file to Cloudinary under `folder`
    (a fixed, server-chosen string per call site - never client-supplied,
    so there's no path-traversal-style concern about what folder a
    caller can write into). Returns Cloudinary's `secure_url`/`public_id`.

    The client file name is never used: Cloudinary generates a random
    public_id (`use_filename=False`, `unique_filename=True`).

    Every route in this codebase is sync `def` except the one place that
    genuinely needs async (the payment webhook, for its exact-raw-body
    requirement - see api/v1/payments.py). This follows the same rule:
    `UploadFile.file` is the underlying SpooledTemporaryFile, readable
    synchronously, so this stays a plain sync call from a sync route.
    """
    _ensure_configured()

    # Read at most one byte past the limit: never buffer an unbounded upload.
    data = file.file.read(MAX_UPLOAD_BYTES + 1)
    validate_image_bytes(data, file.content_type)

    try:
        result = cloudinary.uploader.upload(
            io.BytesIO(data),
            folder=folder,
            resource_type="image",
            use_filename=False,
            unique_filename=True,
            overwrite=False,
        )
    except cloudinary.exceptions.Error as exc:
        # Wrong cloud name/key/secret, quota, or Cloudinary being down. Say
        # which, instead of an unexplained 500 - Cloudinary's message names
        # the problem ("Invalid cloud_name ...") and carries no secret.
        logger.error("IMAGE_UPLOAD_FAILED: %s: %s", type(exc).__name__, exc)
        raise AppException(
            f"Cloudinary rejected the upload: {exc}",
            status_code=502,
            code="UPLOAD_FAILED",
        ) from exc
    return {"secure_url": result["secure_url"], "public_id": result["public_id"]}


_URL_RE = re.compile(
    r"^https://res\.cloudinary\.com/(?P<cloud>[^/]+)/image/upload/(?:[^/]*/)*?(?:v\d+/)?"
    r"(?P<pid>gawachabazaar/[^?#]+?)(?:\.[A-Za-z0-9]{2,5})?$"
)


def public_id_from_url(url: str | None) -> str | None:
    """Cloudinary public_id for an image WE uploaded (our cloud, our
    `gawachabazaar/` folders), else None. External or pasted URLs are never
    touched, so a stray link can never make us delete someone else's asset."""
    if not url:
        return None
    m = _URL_RE.match(url.strip())
    if not m or m.group("cloud") != (settings.CLOUDINARY_CLOUD_NAME or "").strip():
        return None
    return m.group("pid")


def release_image(url: str | None) -> bool:
    """Best-effort removal of a replaced/deleted image from Cloudinary. Call it
    AFTER the database change has committed; a failure is logged and never
    surfaces to the admin (the worst case is one orphaned asset, as before)."""
    public_id = public_id_from_url(url)
    if public_id is None:
        return False
    try:
        _ensure_configured()
        result = cloudinary.uploader.destroy(public_id, resource_type="image", invalidate=True)
        ok = result.get("result") in ("ok", "not found")
        if not ok:
            logger.warning("IMAGE_RELEASE_UNEXPECTED: public_id=%s result=%s", public_id, result)
        return ok
    except Exception as exc:  # noqa: BLE001 - never break an admin action over cleanup
        logger.warning("IMAGE_RELEASE_FAILED: public_id=%s %s", public_id, type(exc).__name__)
        return False
