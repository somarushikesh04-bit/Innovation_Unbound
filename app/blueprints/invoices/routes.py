from flask import Blueprint, request, jsonify, current_app
import json

from app.extensions import db, limiter
from app.models.invoice import Invoice
from app.utils.decorators import auth_required, role_required, get_current_user
from app.models.user import UserRole
from app.services.ocr_service import validate_file, save_upload, extract_text_from_file, parse_invoice_text
from app.services.fraud_detector import check_all_anomalies

invoices_bp = Blueprint("invoices", __name__, url_prefix="/api/invoices")


@invoices_bp.route("", methods=["GET"])
@auth_required
def get_invoices():
    user = get_current_user()
    page = int(request.args.get("page", 1))
    per_page = int(request.args.get("per_page", 20))
    status = request.args.get("status", "")

    q = Invoice.query.filter_by(org_id=user.org_id)
    if status:
        q = q.filter(Invoice.status == status.upper())

    q = q.order_by(Invoice.created_at.desc())
    paginated = q.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        "invoices": [i.to_dict() for i in paginated.items],
        "total": paginated.total,
        "pages": paginated.pages,
        "current_page": page,
        "counts": {
            "pending": Invoice.query.filter_by(org_id=user.org_id, status="PENDING").count(),
            "flagged": Invoice.query.filter_by(org_id=user.org_id, status="FLAGGED").count(),
            "verified": Invoice.query.filter_by(org_id=user.org_id, status="VERIFIED").count(),
        }
    })


@invoices_bp.route("/upload", methods=["POST"])
@role_required(UserRole.STAFF, UserRole.ACCOUNTANT, UserRole.OWNER)
def upload_invoice():
    user = get_current_user()

    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify({"error": "No file selected"}), 400

    # Validate file
    valid, msg = validate_file(file)
    if not valid:
        return jsonify({"error": msg}), 400

    # Save securely
    upload_folder = current_app.config["UPLOAD_FOLDER"]
    file_path = save_upload(file, upload_folder)

    # OCR extraction
    raw_text = extract_text_from_file(file_path)
    parsed = parse_invoice_text(raw_text)

    # Manual override: if OCR confidence is low, use form-provided values
    ocr_confident = len(raw_text.strip()) > 50

    if not ocr_confident or not parsed.get("vendor_name"):
        form_vendor = request.form.get("vendor_name", "").strip()
        if form_vendor:
            parsed["vendor_name"] = form_vendor

    if not ocr_confident or parsed.get("total_amount", 0) == 0:
        form_amount = request.form.get("total_amount", "").strip()
        if form_amount:
            try:
                parsed["total_amount"] = float(form_amount.replace(",", "").replace("₹", ""))
                parsed["subtotal"] = round(parsed["total_amount"] / 1.18, 2)
                parsed["tax_amount"] = round(parsed["total_amount"] - parsed["subtotal"], 2)
            except (ValueError, TypeError):
                pass

    if not ocr_confident or not parsed.get("invoice_number"):
        form_inv_num = request.form.get("invoice_number", "").strip()
        if form_inv_num:
            parsed["invoice_number"] = form_inv_num

    if not ocr_confident or not parsed.get("invoice_date"):
        form_date = request.form.get("invoice_date", "").strip()
        if form_date:
            try:
                from datetime import date as date_type
                parsed["invoice_date"] = date_type.fromisoformat(form_date)
            except (ValueError, TypeError):
                pass

    # Create invoice record
    invoice = Invoice(
        org_id=user.org_id,
        invoice_number=parsed.get("invoice_number"),
        vendor_name=parsed.get("vendor_name") or request.form.get("vendor_name", "Unknown Vendor"),
        vendor_gstin=parsed.get("vendor_gstin"),
        invoice_date=parsed.get("invoice_date"),
        subtotal=parsed.get("subtotal", 0.0),
        tax_amount=parsed.get("tax_amount", 0.0),
        total_amount=parsed.get("total_amount", 0.0),
        status="PENDING",
        file_path=file_path,
        file_original_name=file.filename[:255],
        line_items_json=json.dumps(parsed.get("line_items", [])),
        raw_ocr_text=raw_text[:5000],
    )
    db.session.add(invoice)
    db.session.flush()

    # Run anomaly checks
    flags = check_all_anomalies(invoice, user.org_id)
    invoice.anomaly_flags_json = json.dumps(flags)

    if flags:
        high_flags = [f for f in flags if f.get("severity") == "HIGH"]
        invoice.status = "FLAGGED" if high_flags else "PENDING"

    db.session.commit()

    return jsonify({
        "message": "Invoice uploaded and processed",
        "invoice": invoice.to_dict(),
        "ocr_confidence": ocr_confident,
        "ocr_text_extracted": len(raw_text.strip()) > 0,
        "anomalies_detected": len(flags),
    }), 201


@invoices_bp.route("/<int:invoice_id>", methods=["GET"])
@auth_required
def get_invoice(invoice_id):
    user = get_current_user()
    invoice = Invoice.query.filter_by(id=invoice_id, org_id=user.org_id).first_or_404()
    data = invoice.to_dict()
    data["raw_ocr_text"] = invoice.raw_ocr_text[:2000] if invoice.raw_ocr_text else ""
    return jsonify({"invoice": data})


@invoices_bp.route("/<int:invoice_id>/verify", methods=["POST"])
@role_required(UserRole.ACCOUNTANT, UserRole.OWNER)
def verify_invoice(invoice_id):
    from datetime import datetime
    user = get_current_user()
    invoice = Invoice.query.filter_by(id=invoice_id, org_id=user.org_id).first_or_404()

    invoice.status = "VERIFIED"
    invoice.verified_by = user.id
    invoice.verified_at = datetime.utcnow()

    # Auto-create ledger entry
    from app.models.ledger import LedgerEntry, EntryType, EntryCategory
    entry = LedgerEntry(
        org_id=user.org_id,
        entry_type=EntryType.DEBIT.value,
        category=EntryCategory.OPEX.value,
        amount=invoice.total_amount,
        description=f"Invoice {invoice.invoice_number or 'N/A'} - {invoice.vendor_name or 'Vendor'}",
        party_name=invoice.vendor_name or "",
        reference_date=invoice.invoice_date,
        created_by=user.id,
    )
    db.session.add(entry)
    db.session.commit()

    return jsonify({
        "message": "Invoice verified and ledger entry created",
        "invoice": invoice.to_dict(),
        "ledger_entry": entry.to_dict(),
    })


@invoices_bp.route("/<int:invoice_id>", methods=["DELETE"])
@role_required(UserRole.ACCOUNTANT, UserRole.OWNER)
def delete_invoice(invoice_id):
    user = get_current_user()
    invoice = Invoice.query.filter_by(id=invoice_id, org_id=user.org_id).first_or_404()
    db.session.delete(invoice)
    db.session.commit()
    return jsonify({"message": "Invoice deleted"})


@invoices_bp.route("/<int:invoice_id>/recheck", methods=["POST"])
@role_required(UserRole.ACCOUNTANT, UserRole.OWNER)
def recheck_invoice(invoice_id):
    user = get_current_user()
    invoice = Invoice.query.filter_by(id=invoice_id, org_id=user.org_id).first_or_404()
    flags = check_all_anomalies(invoice, user.org_id)
    invoice.anomaly_flags_json = json.dumps(flags)
    invoice.status = "FLAGGED" if any(f["severity"] == "HIGH" for f in flags) else "PENDING"
    db.session.commit()
    return jsonify({"invoice": invoice.to_dict(), "flags": flags})
