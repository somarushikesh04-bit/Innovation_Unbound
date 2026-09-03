import json
import re
import os
import uuid
from datetime import datetime, date
from flask import current_app
from app.models.invoice import Invoice
from app.extensions import db


GSTIN_PATTERN = re.compile(r"\b\d{2}[A-Z]{5}\d{4}[A-Z]{1}[A-Z\d]{1}[Z]{1}[A-Z\d]{1}\b")
INV_NUM_PATTERN = re.compile(r"(?:invoice|inv|bill)[\s#:\-]*([A-Z0-9\-/]+)", re.IGNORECASE)
AMOUNT_PATTERN = re.compile(r"(?:total|grand\s*total|amount due)[^\d]*(\d[\d,]*\.?\d*)", re.IGNORECASE)
DATE_PATTERN = re.compile(r"\b(\d{1,2})[\/\-\.](\d{1,2})[\/\-\.](\d{2,4})\b")


def parse_invoice_text(raw_text: str) -> dict:
    """Extract structured data from raw OCR text."""
    result = {
        "invoice_number": None,
        "vendor_gstin": None,
        "invoice_date": None,
        "subtotal": 0.0,
        "tax_amount": 0.0,
        "total_amount": 0.0,
        "vendor_name": None,
        "line_items": [],
    }

    # Invoice number
    inv_match = INV_NUM_PATTERN.search(raw_text)
    if inv_match:
        result["invoice_number"] = inv_match.group(1).strip()

    # GSTIN
    gstin_match = GSTIN_PATTERN.search(raw_text)
    if gstin_match:
        result["vendor_gstin"] = gstin_match.group(0)

    # Date
    date_match = DATE_PATTERN.search(raw_text)
    if date_match:
        try:
            d, m, y = int(date_match.group(1)), int(date_match.group(2)), int(date_match.group(3))
            if y < 100:
                y += 2000
            result["invoice_date"] = date(y, m, d)
        except Exception:
            pass

    # Total amount
    amount_match = AMOUNT_PATTERN.search(raw_text)
    if amount_match:
        try:
            result["total_amount"] = float(amount_match.group(1).replace(",", ""))
        except Exception:
            pass

    # Parse line items (look for lines with quantity x price patterns)
    lines = raw_text.split("\n")
    for line in lines:
        line = line.strip()
        if re.search(r"\d+\s*[xX]\s*[\d,]+", line) or re.search(r"[\d,]+\.\d{2}\s*$", line):
            nums = re.findall(r"\d[\d,]*\.?\d*", line)
            if nums and len(nums) >= 1:
                desc = re.sub(r"[\d,\.]+", "", line).strip()
                if desc and len(desc) > 2:
                    try:
                        amount = float(nums[-1].replace(",", ""))
                        result["line_items"].append({"description": desc, "amount": amount})
                    except Exception:
                        pass

    # Estimate subtotal and tax if not found
    if result["total_amount"] > 0 and result["subtotal"] == 0:
        result["subtotal"] = round(result["total_amount"] / 1.18, 2)
        result["tax_amount"] = round(result["total_amount"] - result["subtotal"], 2)

    return result


def extract_text_from_file(file_path: str) -> str:
    """Try Tesseract OCR; fall back gracefully to empty string."""
    ext = os.path.splitext(file_path)[1].lower()
    raw_text = ""

    try:
        import pytesseract
        from PIL import Image

        if ext in (".png", ".jpg", ".jpeg"):
            img = Image.open(file_path)
            raw_text = pytesseract.image_to_string(img)
        elif ext == ".pdf":
            try:
                from pdf2image import convert_from_path
                pages = convert_from_path(file_path, dpi=200)
                for page in pages:
                    raw_text += pytesseract.image_to_string(page) + "\n"
            except Exception:
                raw_text = _extract_pdf_text_fallback(file_path)
    except Exception:
        raw_text = _extract_pdf_text_fallback(file_path) if ext == ".pdf" else ""

    return raw_text


def _extract_pdf_text_fallback(file_path: str) -> str:
    """Attempt basic PDF text extraction without Tesseract."""
    try:
        import io
        with open(file_path, "rb") as f:
            content = f.read()
        text = content.decode("latin-1", errors="ignore")
        # Extract readable ASCII sequences
        chunks = re.findall(r"[A-Za-z0-9\s\.\,\-\:\#\/]{5,}", text)
        return "\n".join(chunks[:200])
    except Exception:
        return ""


def validate_file(file) -> tuple[bool, str]:
    """Validate uploaded file: type and size."""
    if not file:
        return False, "No file provided"

    filename = file.filename or ""
    ext = os.path.splitext(filename)[1].lower().lstrip(".")

    allowed = {"png", "jpg", "jpeg", "pdf"}
    if ext not in allowed:
        return False, f"File type '{ext}' not allowed. Use PNG, JPEG, or PDF."

    # Read first 512 bytes for basic magic number check
    header = file.read(512)
    file.seek(0)

    magic_map = {
        b"\x89PNG": "png",
        b"\xff\xd8\xff": "jpg",
        b"%PDF": "pdf",
    }
    detected = None
    for magic, ftype in magic_map.items():
        if header.startswith(magic):
            detected = ftype
            break

    if detected is None:
        return False, "File content does not match a valid image or PDF format"

    return True, "ok"


def save_upload(file, upload_folder: str) -> str:
    """Save file securely with UUID4 filename."""
    os.makedirs(upload_folder, exist_ok=True)
    ext = os.path.splitext(file.filename)[1].lower()
    safe_name = f"{uuid.uuid4().hex}{ext}"
    save_path = os.path.join(upload_folder, safe_name)
    file.seek(0)
    file.save(save_path)
    return save_path
