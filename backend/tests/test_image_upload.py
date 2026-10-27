"""DEL-15: Cloudinary upload hardening. No network: cloudinary.uploader is stubbed."""

import io

import pytest
from fastapi import UploadFile
from PIL import Image
from sqlalchemy.orm import Session
from starlette.datastructures import Headers

from app.core.config import settings
from app.exceptions.base import BusinessValidationError
from app.models.ad import Ad
from app.services import image_upload
from app.services.ad import AdService

MIME = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp", "GIF": "image/gif"}


def make_image(fmt: str, size=(64, 48)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB" if fmt != "GIF" else "P", size, (200, 30, 30) if fmt != "GIF" else 3).save(buf, fmt)
    return buf.getvalue()


def upload_file(data: bytes, content_type: str, name: str = "../../etc/passwd.png") -> UploadFile:
    return UploadFile(io.BytesIO(data), filename=name, headers=Headers({"content-type": content_type}))


@pytest.fixture
def cloud(monkeypatch):
    monkeypatch.setattr(settings, "CLOUDINARY_CLOUD_NAME", "democloud")
    monkeypatch.setattr(settings, "CLOUDINARY_API_KEY", "key")
    monkeypatch.setattr(settings, "CLOUDINARY_API_SECRET", "secret")
    monkeypatch.setattr(image_upload, "_configured", True)
    calls = {"upload": [], "destroy": []}

    def fake_upload(fileobj, **kw):
        calls["upload"].append((fileobj.read(), kw))
        return {"secure_url": "https://res.cloudinary.com/democloud/image/upload/v1/gawachabazaar/x/abc.png",
                "public_id": "gawachabazaar/x/abc"}

    def fake_destroy(public_id, **kw):
        calls["destroy"].append((public_id, kw))
        return {"result": "ok"}

    monkeypatch.setattr(image_upload.cloudinary.uploader, "upload", fake_upload)
    monkeypatch.setattr(image_upload.cloudinary.uploader, "destroy", fake_destroy)
    return calls


@pytest.mark.parametrize("fmt", ["JPEG", "PNG", "WEBP", "GIF"])
def test_valid_images_of_every_allowed_format_pass(fmt: str) -> None:
    info = image_upload.validate_image_bytes(make_image(fmt), MIME[fmt])
    assert (info.format, info.width, info.height) == (fmt, 64, 48)


def test_declared_type_must_match_the_real_content() -> None:
    with pytest.raises(BusinessValidationError, match="declared as"):
        image_upload.validate_image_bytes(make_image("JPEG"), "image/png")


@pytest.mark.parametrize(
    "payload",
    [b"", b"<?php echo 1; ?>", b"GIF89a not really a gif", b"\x89PNG\r\n\x1a\n" + b"junk" * 50, b"MZ" + b"\x00" * 200],
)
def test_non_images_are_rejected_whatever_the_declared_type(payload: bytes) -> None:
    with pytest.raises(BusinessValidationError):
        image_upload.validate_image_bytes(payload, "image/png")


def test_truncated_image_is_rejected() -> None:
    data = make_image("PNG", (300, 300))
    with pytest.raises(BusinessValidationError):
        image_upload.validate_image_bytes(data[: len(data) // 2], "image/png")


def test_svg_and_other_formats_are_rejected() -> None:
    svg = b'<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20"><script>alert(1)</script></svg>'
    with pytest.raises(BusinessValidationError):
        image_upload.validate_image_bytes(svg, "image/svg+xml")
    buf = io.BytesIO()
    Image.new("RGB", (32, 32)).save(buf, "BMP")
    with pytest.raises(BusinessValidationError, match="Unsupported"):
        image_upload.validate_image_bytes(buf.getvalue(), "image/png")


def test_dimension_limits_and_decompression_bombs() -> None:
    with pytest.raises(BusinessValidationError, match="dimensions"):
        image_upload.validate_image_bytes(make_image("PNG", (8, 8)), "image/png")
    buf = io.BytesIO()
    Image.new("1", (9000, 9000)).save(buf, "PNG")  # tiny on disk, 81 megapixels
    assert len(buf.getvalue()) < 2_000_000
    with pytest.raises(BusinessValidationError, match="dimensions"):
        image_upload.validate_image_bytes(buf.getvalue(), "image/png")


def test_oversize_is_rejected(monkeypatch) -> None:
    monkeypatch.setattr(image_upload, "MAX_UPLOAD_BYTES", 500)
    with pytest.raises(BusinessValidationError, match="too large"):
        image_upload.validate_image_bytes(make_image("PNG", (300, 300)), "image/png")


def test_upload_never_uses_the_client_file_name_and_sends_validated_bytes(cloud) -> None:
    data = make_image("PNG")
    result = image_upload.upload_image(upload_file(data, "image/png"), folder="gawachabazaar/products/1")
    sent, kw = cloud["upload"][0]
    assert sent == data
    assert kw["use_filename"] is False and kw["unique_filename"] is True and kw["overwrite"] is False
    assert kw["folder"] == "gawachabazaar/products/1" and kw["resource_type"] == "image"
    assert result["public_id"] == "gawachabazaar/x/abc"


def test_upload_rejects_a_fake_image_before_calling_cloudinary(cloud) -> None:
    with pytest.raises(BusinessValidationError):
        image_upload.upload_image(upload_file(b"<?php system($_GET[1]); ?>", "image/png"), folder="gawachabazaar/x")
    assert cloud["upload"] == []


@pytest.mark.parametrize(
    "url, expected",
    [
        ("https://res.cloudinary.com/democloud/image/upload/v1700000000/gawachabazaar/products/5/abc123.jpg", "gawachabazaar/products/5/abc123"),
        ("https://res.cloudinary.com/democloud/image/upload/gawachabazaar/ads/zz.png", "gawachabazaar/ads/zz"),
        ("https://res.cloudinary.com/democloud/image/upload/c_fill,w_300/v12/gawachabazaar/offers/o1.webp", "gawachabazaar/offers/o1"),
        ("https://res.cloudinary.com/othercloud/image/upload/v1/gawachabazaar/ads/zz.png", None),  # not our cloud
        ("https://res.cloudinary.com/democloud/image/upload/v1/someone-else/zz.png", None),  # not our folder
        ("https://example.com/gawachabazaar/ads/zz.png", None),
        ("http://res.cloudinary.com/democloud/image/upload/v1/gawachabazaar/ads/zz.png", None),
        ("", None),
        (None, None),
    ],
)
def test_public_id_extraction_only_for_our_own_assets(cloud, url, expected) -> None:
    assert image_upload.public_id_from_url(url) == expected


def test_release_image_destroys_only_our_assets_and_swallows_failures(cloud, monkeypatch) -> None:
    ours = "https://res.cloudinary.com/democloud/image/upload/v1/gawachabazaar/ads/old.png"
    assert image_upload.release_image(ours) is True
    assert cloud["destroy"][0][0] == "gawachabazaar/ads/old"
    assert image_upload.release_image("https://i.imgur.com/other.png") is False
    assert len(cloud["destroy"]) == 1

    def boom(*_a, **_k):
        raise RuntimeError("cloudinary down")

    monkeypatch.setattr(image_upload.cloudinary.uploader, "destroy", boom)
    assert image_upload.release_image(ours) is False  # logged, not raised


def test_replacing_and_deleting_an_ad_releases_the_old_asset(cloud, db_session: Session) -> None:
    old = "https://res.cloudinary.com/democloud/image/upload/v1/gawachabazaar/ads/old.png"
    new = "https://res.cloudinary.com/democloud/image/upload/v1/gawachabazaar/ads/new.png"
    ad = Ad(brand_name="B", image_url=old)
    db_session.add(ad)
    db_session.commit()
    from app.core.roles import ADMIN
    from tests.test_phase_13_cart_orders import _create_user_with_role

    admin = _create_user_with_role(db_session, ADMIN, "img_admin@example.com")
    AdService(db_session).admin_replace_image(ad.id, new, admin.id)
    assert [c[0] for c in cloud["destroy"]] == ["gawachabazaar/ads/old"]
    AdService(db_session).admin_delete_ad(ad.id, admin.id)
    assert [c[0] for c in cloud["destroy"]] == ["gawachabazaar/ads/old", "gawachabazaar/ads/new"]
