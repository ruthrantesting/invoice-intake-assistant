from io import BytesIO

import pytest
from PIL import Image
from reportlab.pdfgen import canvas

from invoice_agent.services.document_service import extract_document_text
from invoice_agent.services.upload_service import validate_invoice_upload


def make_pdf(text: str = "INV-001", *, pages: int = 1) -> bytes:
    output = BytesIO()
    doc = canvas.Canvas(output)
    for _ in range(pages):
        doc.drawString(60, 700, text)
        doc.showPage()
    doc.save()
    return output.getvalue()


def make_image() -> bytes:
    output = BytesIO()
    Image.new("RGB", (320, 120), "white").save(output, format="PNG")
    return output.getvalue()


def test_pdf_embedded_text_extraction_has_page_provenance() -> None:
    data = make_pdf("Invoice number INV-001")
    pages = extract_document_text(data, "application/pdf")
    assert len(pages) == 1
    assert pages[0].page_number == 1
    assert "INV-001" in pages[0].text


def test_image_ocr_handles_png() -> None:
    pages = extract_document_text(make_image(), "image/png")
    assert len(pages) == 1
    assert pages[0].method == "ocr"


def test_upload_rejects_filename_and_signature_mismatch() -> None:
    with pytest.raises(ValueError, match="supported"):
        validate_invoice_upload("invoice.pdf", make_image())


def test_upload_rejects_corrupt_and_encrypted_pdf() -> None:
    with pytest.raises(ValueError, match="corrupt"):
        validate_invoice_upload("broken.pdf", b"%PDF-not-a-pdf")
    with pytest.raises(ValueError):
        validate_invoice_upload("empty.pdf", b"")


def test_mixed_page_pdf_returns_document_text() -> None:
    pages = extract_document_text(make_pdf("Mixed text page"), "application/pdf")
    assert "Mixed text page" in pages[0].text


def test_image_without_any_ocr_engine_is_actionable(monkeypatch) -> None:
    monkeypatch.setattr("invoice_agent.services.document_service.ocr_available", lambda: False)
    with pytest.raises(ValueError, match="OCR is unavailable"):
        extract_document_text(make_image(), "image/png")
