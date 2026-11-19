from dataclasses import dataclass
from io import BytesIO

import magic
from PIL import Image, UnidentifiedImageError
from pypdf import PdfReader

from invoice_agent.config import settings


@dataclass(frozen=True)
class ValidatedUpload:
    media_type: str
    page_count: int | None
    image_size: tuple[int, int] | None


def validate_invoice_upload(filename: str, data: bytes) -> ValidatedUpload:
    if not data:
        raise ValueError("The uploaded file is empty.")
    if len(data) > settings.max_upload_bytes:
        raise ValueError("The uploaded file exceeds the configured size limit.")
    media_type = magic.from_buffer(data, mime=True)
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    accepted = {
        "pdf": "application/pdf",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "heic": "image/heic",
        "heif": "image/heif",
    }
    valid_media_types = {accepted[extension]} if extension in accepted else set()
    if extension in {"heic", "heif"}:
        valid_media_types.update({"image/heic", "image/heif", "image/avif"})
    if extension not in accepted or media_type not in valid_media_types:
        raise ValueError("Only PDF, JPEG, PNG, and HEIC invoice files are supported.")
    if media_type == "application/pdf" and not __import__("shutil").which("tesseract"):
        # Embedded-text PDFs may still be parsed, but scanned pages will be marked OCR unavailable.
        pass
    if media_type == "application/pdf":
        try:
            reader = PdfReader(BytesIO(data), strict=True)
            if reader.is_encrypted:
                raise ValueError("Encrypted PDFs cannot be processed.")
            pages = len(reader.pages)
        except ValueError:
            raise
        except Exception as exc:
            raise ValueError("The PDF is corrupt or unsupported.") from exc
        if pages > settings.max_pdf_pages:
            raise ValueError("The PDF exceeds the configured page limit.")
        return ValidatedUpload(media_type, pages, None)
    try:
        with Image.open(BytesIO(data)) as image:
            width, height = image.size
            if width * height > settings.max_image_pixels:
                raise ValueError("The image exceeds the configured pixel limit.")
            image.verify()
    except ValueError:
        raise
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError("The image is corrupt or unsupported.") from exc
    return ValidatedUpload(media_type, None, (width, height))
