from dataclasses import dataclass
from io import BytesIO

import pypdfium2 as pdfium
from PIL import Image, ImageOps
from pillow_heif import register_heif_opener
from pypdf import PdfReader

from invoice_agent.services.ocr_engine import OCR_UNAVAILABLE_MESSAGE, ocr_available, ocr_image

ALLOWED_IMAGE_MIMES = {"image/jpeg", "image/png", "image/heic", "image/heif"}
register_heif_opener()


@dataclass(frozen=True)
class PageText:
    page_number: int
    text: str
    method: str


def extract_document_text(data: bytes, media_type: str) -> list[PageText]:
    if media_type == "application/pdf":
        return _extract_pdf(data)
    if media_type in ALLOWED_IMAGE_MIMES:
        return [_extract_image(data)]
    raise ValueError("Unsupported document media type.")


def _extract_pdf(data: bytes) -> list[PageText]:
    reader = PdfReader(BytesIO(data))
    text_pages: list[str] = [(page.extract_text() or "").strip() for page in reader.pages]
    renderer = pdfium.PdfDocument(data)
    can_ocr = ocr_available()
    results: list[PageText] = []
    try:
        for index, text in enumerate(text_pages):
            ocr_text = ""
            # OCR every page when an engine exists: embedded image text must not be hidden.
            if can_ocr:
                page = renderer[index]
                try:
                    ocr_text = ocr_image(page.render(scale=2).to_pil())
                finally:
                    page.close()
            combined = "\n".join(part for part in (text, ocr_text) if part)
            if text and ocr_text:
                method = "pdf_text+ocr"
            elif text:
                method = "pdf_text"
            elif can_ocr:
                method = "ocr"
            else:
                method = "ocr_unavailable"
            results.append(PageText(index + 1, combined, method))
    finally:
        renderer.close()
    return results


def _extract_image(data: bytes) -> PageText:
    if not ocr_available():
        raise ValueError(OCR_UNAVAILABLE_MESSAGE)
    try:
        with Image.open(BytesIO(data)) as source:
            image = ImageOps.exif_transpose(source).convert("RGB")
        text = ocr_image(image)
    except Exception as exc:
        raise ValueError("The image could not be decoded for text recognition.") from exc
    return PageText(1, text, "ocr")
