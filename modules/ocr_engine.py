import os
import cv2
import numpy as np
from PIL import Image
import pytesseract
from pdf2image import convert_from_path, convert_from_bytes

# Point to Tesseract executable on Windows
if os.name == "nt":
    tesseract_path = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    if os.path.exists(tesseract_path):
        pytesseract.pytesseract.tesseract_cmd = tesseract_path

# Pages processed per batch — keeps RAM use flat for large PDFs
_BATCH_SIZE = 25


def _preprocess_image(img: Image.Image) -> Image.Image:
    arr = np.array(img.convert("RGB"))
    gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
    denoised = cv2.fastNlMeansDenoising(gray, h=10)
    _, thresh = cv2.threshold(denoised, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return Image.fromarray(thresh)


def _ocr_image(img: Image.Image) -> str:
    processed = _preprocess_image(img)
    cfg = "--oem 3 --psm 6 -l eng+hin"
    try:
        return pytesseract.image_to_string(processed, config=cfg)
    except Exception:
        return ""


def _dpi_for_page_count(total_pages: int) -> int:
    """Lower DPI for large PDFs to avoid OOM while keeping accuracy acceptable."""
    if total_pages <= 10:
        return 250
    if total_pages <= 25:
        return 200
    return 150


def _total_pages(path: str) -> int:
    """Return total page count without loading images."""
    try:
        from pdf2image.pdf2image import pdfinfo_from_path
        info = pdfinfo_from_path(path)
        return info.get("Pages", 1)
    except Exception:
        return 0          # unknown → will fall back to full load


def extract_text_from_image(path: str) -> str:
    img = Image.open(path)
    return _ocr_image(img)


def extract_text_from_pdf(path: str) -> str:
    total = _total_pages(path)
    dpi = _dpi_for_page_count(total) if total else 200
    all_text: list[str] = []

    if total == 0:
        # pdfinfo unavailable — load all at once (small PDF assumed)
        try:
            pages = convert_from_path(path, dpi=dpi)
        except Exception:
            with open(path, "rb") as f:
                pages = convert_from_bytes(f.read(), dpi=dpi)
        for page in pages:
            all_text.append(_ocr_image(page))
    else:
        # Batch-load to keep memory constant regardless of page count
        for start in range(1, total + 1, _BATCH_SIZE):
            end = min(start + _BATCH_SIZE - 1, total)
            try:
                batch = convert_from_path(
                    path, dpi=dpi, first_page=start, last_page=end
                )
            except Exception:
                with open(path, "rb") as f:
                    batch = convert_from_bytes(
                        f.read(), dpi=dpi, first_page=start, last_page=end
                    )
            for page_img in batch:
                text = _ocr_image(page_img)
                all_text.append(text)
                page_img.close()       # release image memory immediately

    return "\n\n--- PAGE BREAK ---\n\n".join(all_text)


def extract_text(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    if ext == ".pdf":
        return extract_text_from_pdf(path)
    elif ext in (".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".webp"):
        return extract_text_from_image(path)
    else:
        raise ValueError(f"Unsupported file type: {ext}")
