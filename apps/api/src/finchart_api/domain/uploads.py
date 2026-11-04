from finchart_api.imaging import InvalidImageError, detect_mime

ALLOWED_MIME = frozenset({"image/png", "image/jpeg", "image/webp"})


class UploadTooLargeError(ValueError):
    pass


class UnsupportedImageError(ValueError):
    pass


def check_declared_mime(mime: str | None) -> None:
    if mime not in ALLOWED_MIME:
        raise UnsupportedImageError(mime)


def validate_image_upload(data: bytes, max_bytes: int) -> None:
    """Shared by the web upload and the Telegram bot: size limit plus a real format sniff."""
    if len(data) > max_bytes:
        raise UploadTooLargeError(len(data))
    try:
        mime = detect_mime(data)
    except InvalidImageError as exc:
        raise UnsupportedImageError("not a readable image") from exc
    if mime not in ALLOWED_MIME:
        raise UnsupportedImageError(mime)
