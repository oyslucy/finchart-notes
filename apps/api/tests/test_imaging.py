import io

import pytest
from PIL import Image

from finchart_api.imaging import (
    MIN_CROP_SIDE_PX,
    CropRejectedError,
    InvalidImageError,
    bbox_to_pixels,
    detect_mime,
    pad_box,
    prepare_card_images,
    sha256_hex,
    validate_crop,
)


def test_sha256_is_stable(png_bytes: bytes) -> None:
    assert sha256_hex(png_bytes) == sha256_hex(bytes(png_bytes))
    assert len(sha256_hex(png_bytes)) == 64


@pytest.mark.parametrize(
    ("bbox", "expected"),
    [
        ([0, 0, 1000, 1000], (0, 0, 1000, 800)),
        ([250, 100, 875, 600], (100, 200, 600, 700)),
        ([1, 1, 999, 999], (1, 0, 999, 800)),
        ([-50, -10, 1200, 1100], (0, 0, 1000, 800)),
    ],
)
def test_bbox_to_pixels(bbox: list[int], expected: tuple[int, int, int, int]) -> None:
    assert bbox_to_pixels(bbox, 1000, 800) == expected


def test_crop_at_min_side_is_accepted() -> None:
    validate_crop((0, 0, MIN_CROP_SIDE_PX, MIN_CROP_SIDE_PX), 1000, 1000)


def test_crop_below_min_side_is_rejected() -> None:
    with pytest.raises(CropRejectedError):
        validate_crop((0, 0, MIN_CROP_SIDE_PX - 1, 500), 1000, 1000)


def test_crop_just_under_ninety_percent_is_accepted() -> None:
    validate_crop((0, 0, 1000, 899), 1000, 1000)


def test_crop_at_ninety_percent_is_rejected() -> None:
    with pytest.raises(CropRejectedError):
        validate_crop((0, 0, 1000, 900), 1000, 1000)


def test_prepare_crops_to_bbox(png_bytes: bytes) -> None:
    prepared = prepare_card_images(png_bytes, [250, 100, 875, 600])

    assert prepared.cropped
    # 500x500 box plus a 0.8% margin on each side (8px horizontally, 6px vertically)
    assert (prepared.width, prepared.height) == (516, 512)
    assert Image.open(io.BytesIO(prepared.image)).format == "WEBP"
    assert max(Image.open(io.BytesIO(prepared.thumb)).size) <= 480


def test_prepare_keeps_full_image_when_crop_rejected(png_bytes: bytes) -> None:
    prepared = prepare_card_images(png_bytes, [0, 0, 1000, 1000])

    assert not prepared.cropped
    assert (prepared.width, prepared.height) == (1000, 800)


def test_prepare_strips_exif() -> None:
    exif = Image.Exif()
    exif[0x010F] = "SecretCam"
    buf = io.BytesIO()
    Image.new("RGB", (800, 600), "white").save(buf, format="JPEG", exif=exif)

    prepared = prepare_card_images(buf.getvalue(), [100, 100, 800, 800])

    assert not Image.open(io.BytesIO(prepared.image)).getexif()
    assert b"SecretCam" not in prepared.image


def test_detect_mime_rejects_non_images() -> None:
    with pytest.raises(InvalidImageError):
        detect_mime(b"not an image")


def test_detect_mime_rejects_unsupported_format() -> None:
    buf = io.BytesIO()
    Image.new("RGB", (10, 10)).save(buf, format="GIF")
    with pytest.raises(InvalidImageError):
        detect_mime(buf.getvalue())


def test_pad_box_expands_and_clamps() -> None:
    assert pad_box((100, 200, 600, 700), 1000, 800) == (92, 194, 608, 706)
    assert pad_box((0, 0, 1000, 800), 1000, 800) == (0, 0, 1000, 800)
