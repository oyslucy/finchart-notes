from finchart_api.imaging import InvalidImageError, detect_mime
from finchart_api.pdf import InvalidPdfError, pdf_page_count

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


class UnsupportedPdfError(ValueError):
    pass


class TooManyPagesError(ValueError):
    def __init__(self, pages: int, limit: int) -> None:
        super().__init__(f"{pages} pages, limit {limit}")
        self.pages, self.limit = pages, limit


def validate_pdf_upload(data: bytes, max_bytes: int, max_pages: int) -> int:
    """Shared by the web upload and the Telegram bot; returns the page count."""
    if len(data) > max_bytes:
        raise UploadTooLargeError(len(data))
    try:
        pages = pdf_page_count(data)
    except InvalidPdfError as exc:
        raise UnsupportedPdfError(str(exc)) from exc
    if pages == 0:
        raise UnsupportedPdfError("no pages")
    if pages > max_pages:
        raise TooManyPagesError(pages, max_pages)
    return pages
