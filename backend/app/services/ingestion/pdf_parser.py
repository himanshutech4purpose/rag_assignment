"""PDF text extraction utilities."""

import io
from typing import Any

from pypdf import PdfReader

from app.exceptions import ValidationError
from app.logging_config import get_logger

logger = get_logger(__name__)

PDF_MAGIC_BYTES = b"%PDF"


def _validate_pdf_magic_bytes(data: bytes) -> None:
    if not data.startswith(PDF_MAGIC_BYTES):
        raise ValidationError("File does not appear to be a valid PDF")


def _count_images(page) -> int:
    """Count inline images on a PDF page.

    pypdf exposes page images via ``page.images``. Some PDF structures can
    trigger errors while iterating; in that case we fall back to counting
    image resources in the page's ``/XObject`` dictionary.
    """
    try:
        return len(page.images)
    except Exception:
        try:
            resources = page.get("/Resources") or {}
            xobjects = resources.get("/XObject") or {}
            return sum(
                1
                for obj in xobjects.get_object().values()
                if obj.get_object().get("/Subtype") == "/Image"
            )
        except Exception:
            return 0


def extract_text(file_bytes: bytes) -> tuple[list[dict[str, Any]], int]:
    """Extract text from PDF bytes.

    Returns a tuple of:
      - a list of dicts with `page_number`, `text`, and `image_count` keys;
      - the total number of images found in the PDF.
    """
    _validate_pdf_magic_bytes(file_bytes)
    reader = PdfReader(io.BytesIO(file_bytes))
    pages = []
    total_images = 0
    for i, page in enumerate(reader.pages, start=1):
        text = page.extract_text()
        image_count = _count_images(page)
        total_images += image_count
        pages.append({"page_number": i, "text": text, "image_count": image_count})
    if total_images > 0:
        logger.info("Found %d image(s) in PDF; image content is ignored", total_images)
    return pages, total_images
