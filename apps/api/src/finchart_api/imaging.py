import hashlib
import io
from dataclasses import dataclass

from PIL import Image, ImageOps

# Caps decoded size so a small but huge-dimension upload cannot exhaust the 1 GB VM.
Image.MAX_IMAGE_PIXELS = 40_000_000

MIN_CROP_SIDE_PX = 64
# VLM boxes tend to hug the plot tightly and clip axis labels, so crops get a small margin.
CROP_PAD_RATIO = 0.008
MAX_CROP_AREA_RATIO = 0.9
THUMB_MAX_SIDE_PX = 480
WEBP_QUALITY = 90

_MIME_BY_FORMAT = {"PNG": "image/png", "JPEG": "image/jpeg", "WEBP": "image/webp"}

PixelBox = tuple[int, int, int, int]


class InvalidImageError(ValueError):
    pass


class CropRejectedError(ValueError):
    pass


@dataclass(frozen=True)
class PreparedImages:
    image: bytes
    thumb: bytes
    cropped: bool
    width: int
    height: int


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def detect_mime(data: bytes) -> str:
    try:
        with Image.open(io.BytesIO(data)) as img:
            fmt = img.format
    except Exception as exc:
        raise InvalidImageError("not a readable image") from exc
    mime = _MIME_BY_FORMAT.get(fmt or "")
    if mime is None:
        raise InvalidImageError(f"unsupported image format: {fmt}")
    return mime


def load_image(data: bytes) -> Image.Image:
    """Decodes, applies EXIF orientation, and returns an RGB(A) image without metadata."""
    try:
        source = Image.open(io.BytesIO(data))
        source.load()
    except Exception as exc:
        raise InvalidImageError("not a readable image") from exc
    img = ImageOps.exif_transpose(source)
    mode = "RGBA" if img.mode in ("RGBA", "LA", "P") else "RGB"
    clean = Image.new(mode, img.size)
    clean.paste(img.convert(mode))
    return clean


def bbox_to_pixels(bbox: list[int], width: int, height: int) -> PixelBox:
    """Maps [ymin, xmin, ymax, xmax] on a 0-1000 grid to a (left, top, right, bottom) box."""
    ymin, xmin, ymax, xmax = (min(max(v, 0), 1000) for v in bbox)
    left = xmin * width // 1000
    top = ymin * height // 1000
    right = -(-xmax * width // 1000)
    bottom = -(-ymax * height // 1000)
    return left, top, min(right, width), min(bottom, height)


def pad_box(box: PixelBox, width: int, height: int, ratio: float = CROP_PAD_RATIO) -> PixelBox:
    left, top, right, bottom = box
    pad_x, pad_y = round(width * ratio), round(height * ratio)
    return (
        max(left - pad_x, 0),
        max(top - pad_y, 0),
        min(right + pad_x, width),
        min(bottom + pad_y, height),
    )


def validate_crop(box: PixelBox, width: int, height: int) -> None:
    left, top, right, bottom = box
    crop_w, crop_h = right - left, bottom - top
    if crop_w < MIN_CROP_SIDE_PX or crop_h < MIN_CROP_SIDE_PX:
        raise CropRejectedError(f"crop too small: {crop_w}x{crop_h}")
    if crop_w * crop_h >= MAX_CROP_AREA_RATIO * width * height:
        raise CropRejectedError("crop covers almost the whole image")


def encode_webp(img: Image.Image, quality: int = WEBP_QUALITY) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="WEBP", quality=quality, method=4)
    return buf.getvalue()


def make_thumbnail(img: Image.Image, max_side: int = THUMB_MAX_SIDE_PX) -> Image.Image:
    thumb = img.copy()
    thumb.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
    return thumb


def prepare_card_images(data: bytes, bbox: list[int]) -> PreparedImages:
    """Crops to bbox when the box is plausible, otherwise keeps the full image."""
    img = load_image(data)
    box = bbox_to_pixels(bbox, img.width, img.height)
    try:
        validate_crop(box, img.width, img.height)
        target, cropped = img.crop(pad_box(box, img.width, img.height)), True
    except CropRejectedError:
        target, cropped = img, False
    return PreparedImages(
        image=encode_webp(target),
        thumb=encode_webp(make_thumbnail(target), quality=80),
        cropped=cropped,
        width=target.width,
        height=target.height,
    )
