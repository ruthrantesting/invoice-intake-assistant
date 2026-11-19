"""Local OCR abstraction: Tesseract when installed, otherwise bundled RapidOCR (ONNX)."""

import shutil
from functools import lru_cache
from statistics import median

import numpy as np
import pytesseract
from PIL import Image

OCR_UNAVAILABLE_MESSAGE = "OCR is unavailable because no OCR engine is installed."


@lru_cache(maxsize=1)
def _rapidocr():
    try:
        from rapidocr_onnxruntime import RapidOCR

        return RapidOCR()
    except Exception:  # pragma: no cover - depends on optional runtime
        return None


def ocr_engine_name() -> str | None:
    if shutil.which("tesseract") is not None:
        return "tesseract"
    if _rapidocr() is not None:
        return "rapidocr"
    return None


def ocr_available() -> bool:
    return ocr_engine_name() is not None


def ocr_image(image: Image.Image) -> str:
    """Return reading-order text; raises ValueError when no engine is available."""
    engine = ocr_engine_name()
    if engine == "tesseract":
        return pytesseract.image_to_string(image).strip()
    if engine == "rapidocr":
        return _rapidocr_text(image.convert("RGB"))
    raise ValueError(OCR_UNAVAILABLE_MESSAGE)


def _rapidocr_text(image: Image.Image) -> str:
    result, _ = _rapidocr()(np.array(image))
    if not result:
        return ""
    items = []
    for box, text, _confidence in result:
        ys = [point[1] for point in box]
        xs = [point[0] for point in box]
        items.append((sum(ys) / len(ys), max(ys) - min(ys), min(xs), str(text).strip()))
    items = [item for item in items if item[3]]
    if not items:
        return ""
    tolerance = max(4.0, median(item[1] for item in items) * 0.6)
    items.sort(key=lambda item: item[0])
    lines: list[list[tuple[float, float, float, str]]] = []
    for item in items:
        if lines and abs(item[0] - _line_center(lines[-1])) <= tolerance:
            lines[-1].append(item)
        else:
            lines.append([item])
    return "\n".join(
        "  ".join(part[3] for part in sorted(line, key=lambda part: part[2])) for line in lines
    )


def _line_center(line: list[tuple[float, float, float, str]]) -> float:
    return sum(part[0] for part in line) / len(line)
