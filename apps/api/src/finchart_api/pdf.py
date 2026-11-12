import io

from pypdf import PdfReader
from pypdf.errors import PdfReadError


class InvalidPdfError(ValueError):
    pass


def pdf_page_count(data: bytes) -> int:
    """Reads only the page tree; nothing is rendered, so it stays light on the 1 GB VM."""
    if not data.startswith(b"%PDF-"):
        raise InvalidPdfError("not a pdf")
    try:
        reader = PdfReader(io.BytesIO(data))
        encrypted = reader.is_encrypted
        pages = 0 if encrypted else len(reader.pages)
    except (PdfReadError, ValueError, KeyError, TypeError) as exc:
        raise InvalidPdfError("unreadable") from exc
    if encrypted:
        raise InvalidPdfError("encrypted")
    return pages
