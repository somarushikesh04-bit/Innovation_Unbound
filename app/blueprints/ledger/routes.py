from flask import Blueprint, request, jsonify
from datetime import date
import json
import io
import csv

from app.extensions import db
from app.models.ledger import LedgerEntry, EntryType, EntryCategory
from app.models.directory import CustomerSupplier, InventoryItem
from app.utils.decorators import auth_required, role_required, get_current_user
from app.models.user import UserRole

ledger_bp = Blueprint("ledger", __name__, url_prefix="/api/ledger")


@ledger_bp.route("/entries", methods=["GET"])
@auth_required
def get_entries():
    user = get_current_user()
    page = int(request.args.get("page", 1))
    per_page = int(request.args.get("per_page", 25))
    category = request.args.get("category")
    entry_type = request.args.get("entry_type")
    search = request.args.get("search", "")
    date_from = request.args.get("date_from")
    date_to = request.args.get("date_to")

    q = LedgerEntry.query.filter_by(org_id=user.org_id)

    if category:
        q = q.filter(LedgerEntry.category == category.upper())
    if entry_type:
        q = q.filter(LedgerEntry.entry_type == entry_type.upper())
    if search:
        q = q.filter(LedgerEntry.description.ilike(f"%{search}%"))
    if date_from:
        q = q.filter(LedgerEntry.reference_date >= date_from)
    if date_to:
        q = q.filter(LedgerEntry.reference_date <= date_to)

    q = q.order_by(LedgerEntry.reference_date.desc(), LedgerEntry.id.desc())
    paginated = q.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        "entries": [e.to_dict() for e in paginated.items],
        "total": paginated.total,
        "pages": paginated.pages,
        "current_page": page,
        "categories": [c.value for c in EntryCategory],
    })


@ledger_bp.route("/entries", methods=["POST"])
@role_required(UserRole.STAFF, UserRole.ACCOUNTANT, UserRole.OWNER)
def create_entry():
    user = get_current_user()
    data = request.get_json(silent=True) or {}

    required = ["entry_type", "category", "amount"]
    for f in required:
        if not data.get(f):
            return jsonify({"error": f"Field '{f}' is required"}), 400

    try:
        amount = float(data["amount"])
        if amount <= 0:
            raise ValueError
    except (ValueError, TypeError):
        return jsonify({"error": "Amount must be a positive number"}), 400

    ref_date = date.today()
    if data.get("reference_date"):
        try:
            ref_date = date.fromisoformat(data["reference_date"])
        except ValueError:
            pass

    entry = LedgerEntry(
        org_id=user.org_id,
        entry_type=data["entry_type"].upper(),
        category=data["category"].upper(),
        amount=amount,
        description=str(data.get("description", ""))[:500],
        party_name=str(data.get("party_name", ""))[:200],
        reference_date=ref_date,
        created_by=user.id,
    )
    db.session.add(entry)
    db.session.commit()

    return jsonify({"message": "Entry created", "entry": entry.to_dict()}), 201


@ledger_bp.route("/entries/<int:entry_id>", methods=["DELETE"])
@role_required(UserRole.ACCOUNTANT, UserRole.OWNER)
def delete_entry(entry_id):
    user = get_current_user()
    entry = LedgerEntry.query.filter_by(id=entry_id, org_id=user.org_id).first_or_404()
    db.session.delete(entry)
    db.session.commit()
    return jsonify({"message": "Entry deleted"})


@ledger_bp.route("/bulk-import", methods=["POST"])
@role_required(UserRole.ACCOUNTANT, UserRole.OWNER)
def bulk_import():
    user = get_current_user()
    if "file" not in request.files:
        return jsonify({"error": "CSV file required"}), 400

    f = request.files["file"]
    content = f.read().decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(content))

    imported = 0
    errors = []
    category_map = {c.value.lower(): c.value for c in EntryCategory}
    type_map = {"debit": "DEBIT", "credit": "CREDIT", "dr": "DEBIT", "cr": "CREDIT"}

    for i, row in enumerate(reader, start=2):
        try:
            row = {k.strip().lower(): v.strip() for k, v in row.items() if k}
            amount_str = row.get("amount") or row.get("debit") or row.get("credit") or "0"
            amount = float(str(amount_str).replace(",", "").replace("₹", "").strip() or 0)
            if amount <= 0:
                continue

            entry_type_raw = row.get("type") or row.get("entry_type") or ("DEBIT" if row.get("debit") else "CREDIT")
            entry_type = type_map.get(entry_type_raw.lower(), "DEBIT")

            cat_raw = row.get("category") or "other"
            category = category_map.get(cat_raw.lower(), EntryCategory.OTHER.value)

            desc = row.get("description") or row.get("narration") or row.get("particulars") or ""
            party = row.get("party") or row.get("vendor") or row.get("customer") or ""

            ref_date = date.today()
            date_str = row.get("date") or row.get("reference_date") or ""
            if date_str:
                for fmt in ("%d-%m-%Y", "%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"):
                    try:
                        from datetime import datetime as dt
                        ref_date = dt.strptime(date_str, fmt).date()
                        break
                    except ValueError:
                        continue

            entry = LedgerEntry(
                org_id=user.org_id,
                entry_type=entry_type,
                category=category,
                amount=amount,
                description=str(desc)[:500],
                party_name=str(party)[:200],
                reference_date=ref_date,
                created_by=user.id,
            )
            db.session.add(entry)
            imported += 1
        except Exception as e:
            errors.append(f"Row {i}: {str(e)}")

    db.session.commit()
    return jsonify({"message": f"Imported {imported} entries", "errors": errors[:10]})


@ledger_bp.route("/summary", methods=["GET"])
@auth_required
def get_summary():
    user = get_current_user()
    from app.services.forecasting import get_ledger_aggregates, compute_runway, compute_health_score
    agg = get_ledger_aggregates(user.org_id, 90)
    runway = compute_runway(user.org_id)
    health = compute_health_score(user.org_id)
    return jsonify({"aggregates": agg, "runway": runway, "health": health})


# ── Directory: Customers & Suppliers ──────────────────────────────────────────

@ledger_bp.route("/directory", methods=["GET"])
@auth_required
def get_directory():
    user = get_current_user()
    entity_type = request.args.get("type", "").upper()
    q = CustomerSupplier.query.filter_by(org_id=user.org_id)
    if entity_type in ("CUSTOMER", "SUPPLIER"):
        q = q.filter_by(entity_type=entity_type)
    items = q.order_by(CustomerSupplier.name).all()
    return jsonify({"contacts": [c.to_dict() for c in items]})


@ledger_bp.route("/directory", methods=["POST"])
@role_required(UserRole.STAFF, UserRole.ACCOUNTANT, UserRole.OWNER)
def create_contact():
    user = get_current_user()
    data = request.get_json(silent=True) or {}
    if not data.get("name") or not data.get("entity_type"):
        return jsonify({"error": "Name and entity_type are required"}), 400

    contact = CustomerSupplier(
        org_id=user.org_id,
        entity_type=data["entity_type"].upper(),
        name=str(data["name"])[:200],
        gstin=data.get("gstin", "")[:20],
        phone=data.get("phone", "")[:20],
        email=data.get("email", "")[:255],
        payment_terms_days=int(data.get("payment_terms_days", 30)),
        outstanding_balance=float(data.get("outstanding_balance", 0)),
    )
    db.session.add(contact)
    db.session.commit()
    return jsonify({"message": "Contact created", "contact": contact.to_dict()}), 201


@ledger_bp.route("/directory/<int:contact_id>", methods=["DELETE"])
@role_required(UserRole.STAFF, UserRole.ACCOUNTANT, UserRole.OWNER)
def delete_contact(contact_id):
    user = get_current_user()
    contact = CustomerSupplier.query.filter_by(id=contact_id, org_id=user.org_id).first_or_404()
    db.session.delete(contact)
    db.session.commit()
    return jsonify({"message": "Contact deleted"})


# ── Inventory ─────────────────────────────────────────────────────────────────

@ledger_bp.route("/inventory", methods=["GET"])
@auth_required
def get_inventory():
    user = get_current_user()
    items = InventoryItem.query.filter_by(org_id=user.org_id).order_by(InventoryItem.name).all()
    low_stock_count = sum(1 for i in items if i.is_low_stock)
    return jsonify({"items": [i.to_dict() for i in items], "low_stock_count": low_stock_count})


@ledger_bp.route("/inventory", methods=["POST"])
@role_required(UserRole.STAFF, UserRole.ACCOUNTANT, UserRole.OWNER)
def create_inventory_item():
    user = get_current_user()
    data = request.get_json(silent=True) or {}
    if not data.get("name"):
        return jsonify({"error": "Item name is required"}), 400

    item = InventoryItem(
        org_id=user.org_id,
        sku=data.get("sku", ""),
        name=str(data["name"])[:200],
        unit_volume=int(data.get("unit_volume", 0)),
        unit_cost=float(data.get("unit_cost", 0)),
        selling_price=float(data.get("selling_price", 0)),
        turnover_frequency_days=float(data.get("turnover_frequency_days", 30)),
        reorder_threshold=int(data.get("reorder_threshold", 10)),
    )
    db.session.add(item)
    db.session.commit()
    return jsonify({"message": "Item created", "item": item.to_dict()}), 201


@ledger_bp.route("/inventory/<int:item_id>", methods=["DELETE"])
@role_required(UserRole.STAFF, UserRole.ACCOUNTANT, UserRole.OWNER)
def delete_inventory_item(item_id):
    user = get_current_user()
    item = InventoryItem.query.filter_by(id=item_id, org_id=user.org_id).first_or_404()
    db.session.delete(item)
    db.session.commit()
    return jsonify({"message": "Item deleted"})


@ledger_bp.route("/entries/clear-all", methods=["DELETE"])
@role_required(UserRole.ACCOUNTANT, UserRole.OWNER)
def clear_all_entries():
    """Delete ALL ledger entries for this org (useful to reset demo data)."""
    user = get_current_user()
    count = LedgerEntry.query.filter_by(org_id=user.org_id).delete()
    db.session.commit()
    return jsonify({"message": f"Deleted {count} ledger entries", "deleted": count})

