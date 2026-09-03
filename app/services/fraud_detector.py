"""
Fraud & Anomaly Detection Engine for invoice validation.
Checks:
  1. Duplicate invoice detection (same number or same amount ± 7 days same vendor)
  2. Tax / math discrepancy (subtotal + tax != total)
  3. Spend spike detection (> 2σ from 90-day vendor baseline)
  4. GSTIN format validation
"""
import json
import re
from datetime import timedelta
from sqlalchemy import func, and_

from app.models.invoice import Invoice
from app.extensions import db

GSTIN_RE = re.compile(r"^[0-3][0-9][A-Z]{5}[0-9]{4}[A-Z]{1}[A-Z0-9]{1}Z[A-Z0-9]{1}$")


def check_all_anomalies(invoice: Invoice, org_id: int) -> list[dict]:
    """Run all anomaly checks and return a list of flag dicts."""
    flags = []
    flags.extend(_check_duplicate(invoice, org_id))
    flags.extend(_check_math_discrepancy(invoice))
    flags.extend(_check_spend_spike(invoice, org_id))
    flags.extend(_check_gstin(invoice))
    return flags


def _check_duplicate(invoice: Invoice, org_id: int) -> list[dict]:
    flags = []

    if invoice.invoice_number:
        dup = Invoice.query.filter(
            Invoice.org_id == org_id,
            Invoice.invoice_number == invoice.invoice_number,
            Invoice.id != (invoice.id or -1),
        ).first()
        if dup:
            flags.append({
                "type": "DUPLICATE_INVOICE_NUMBER",
                "severity": "HIGH",
                "message": f"Invoice number '{invoice.invoice_number}' already exists (ID: {dup.id}).",
                "confidence": 0.97,
            })

    # Same amount ± 7 days for same vendor
    if invoice.vendor_name and invoice.total_amount and invoice.invoice_date:
        window_start = invoice.invoice_date - timedelta(days=7)
        window_end = invoice.invoice_date + timedelta(days=7)
        amount_low = invoice.total_amount * 0.99
        amount_high = invoice.total_amount * 1.01

        dup_amount = Invoice.query.filter(
            Invoice.org_id == org_id,
            Invoice.vendor_name == invoice.vendor_name,
            Invoice.total_amount.between(amount_low, amount_high),
            Invoice.invoice_date.between(window_start, window_end),
            Invoice.id != (invoice.id or -1),
        ).first()
        if dup_amount:
            flags.append({
                "type": "DUPLICATE_AMOUNT_DATE_WINDOW",
                "severity": "MEDIUM",
                "message": f"Similar amount ₹{invoice.total_amount:,.2f} from '{invoice.vendor_name}' within ±7 days (ID: {dup_amount.id}).",
                "confidence": 0.82,
            })

    return flags


def _check_math_discrepancy(invoice: Invoice) -> list[dict]:
    flags = []

    if invoice.subtotal > 0 and invoice.tax_amount >= 0 and invoice.total_amount > 0:
        computed = round(invoice.subtotal + invoice.tax_amount, 2)
        if abs(computed - invoice.total_amount) > 1.0:
            flags.append({
                "type": "TAX_MATH_DISCREPANCY",
                "severity": "HIGH",
                "message": f"Subtotal ({invoice.subtotal:,.2f}) + Tax ({invoice.tax_amount:,.2f}) = {computed:,.2f}, but total is {invoice.total_amount:,.2f}.",
                "confidence": 0.99,
            })

    return flags


def _check_spend_spike(invoice: Invoice, org_id: int) -> list[dict]:
    """Compare invoice total against 90-day vendor baseline (mean ± 2σ)."""
    flags = []

    if not invoice.vendor_name or not invoice.total_amount:
        return flags

    from datetime import date, timedelta
    cutoff = None
    if invoice.invoice_date:
        cutoff = invoice.invoice_date - timedelta(days=90)

    query = Invoice.query.filter(
        Invoice.org_id == org_id,
        Invoice.vendor_name == invoice.vendor_name,
        Invoice.status != "FLAGGED",
    )
    if cutoff:
        query = query.filter(Invoice.invoice_date >= cutoff)

    amounts = [r.total_amount for r in query.all() if r.id != (invoice.id or -1)]

    if len(amounts) >= 3:
        mean = sum(amounts) / len(amounts)
        variance = sum((x - mean) ** 2 for x in amounts) / len(amounts)
        std = variance ** 0.5
        threshold = mean + 2.0 * std

        if invoice.total_amount > threshold:
            flags.append({
                "type": "SPEND_SPIKE",
                "severity": "MEDIUM",
                "message": f"Amount ₹{invoice.total_amount:,.2f} is {((invoice.total_amount - mean) / std):.1f}σ above 90-day baseline of ₹{mean:,.2f} for vendor '{invoice.vendor_name}'.",
                "confidence": 0.75,
            })

    return flags


def _check_gstin(invoice: Invoice) -> list[dict]:
    flags = []

    if invoice.vendor_gstin:
        gstin = invoice.vendor_gstin.strip().upper()
        if not GSTIN_RE.match(gstin):
            flags.append({
                "type": "INVALID_GSTIN_FORMAT",
                "severity": "LOW",
                "message": f"GSTIN '{invoice.vendor_gstin}' does not match standard 15-character format.",
                "confidence": 0.95,
            })

    return flags
