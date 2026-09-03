"""
app/blueprints/smartshield/routes.py
SmartShield API Routes — AI Banking Fraud Protection
"""
import json
from datetime import datetime
from flask import Blueprint, request, jsonify

from app.extensions import db, limiter
from app.utils.decorators import auth_required, get_current_user
from app.models.shield import FraudTransaction, TrustedContact, ScamReport, RiskLevel, TransactionStatus
from app.services.smartshield_service import (
    analyze_transaction, fraud_chatbot, get_shield_stats, send_trusted_contact_alert
)

shield_bp = Blueprint("smartshield", __name__, url_prefix="/api/shield")


@shield_bp.route("/analyze", methods=["POST"])
@auth_required
@limiter.limit("30 per minute")
def analyze():
    """Analyze a transaction for fraud risk."""
    user = get_current_user()
    data = request.get_json(silent=True) or {}

    amount = data.get("amount")
    recipient_name = (data.get("recipient_name") or "").strip()

    if not amount or not recipient_name:
        return jsonify({"error": "amount and recipient_name are required"}), 400

    try:
        amount = float(amount)
        if amount <= 0:
            return jsonify({"error": "Amount must be positive"}), 400
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid amount"}), 400

    # Run fraud analysis
    result = analyze_transaction(
        org_id=user.org_id,
        amount=amount,
        recipient_name=recipient_name,
        recipient_id=data.get("recipient_id", ""),
        payment_method=data.get("payment_method", "UPI"),
        description=data.get("description", ""),
        device_id=data.get("device_id", request.remote_addr),
        location=data.get("location", ""),
        transaction_hour=data.get("transaction_hour"),
        vulnerable_user=bool(data.get("vulnerable_user_mode", False)),
    )

    # Persist transaction record
    txn = FraudTransaction(
        org_id=user.org_id,
        user_id=user.id,
        amount=amount,
        recipient_name=recipient_name,
        recipient_id=data.get("recipient_id", ""),
        payment_method=data.get("payment_method", "UPI"),
        description=data.get("description", ""),
        device_id=data.get("device_id", ""),
        location=data.get("location", ""),
        transaction_hour=result.get("transaction_hour", datetime.utcnow().hour),
        risk_score=result["risk_score"],
        risk_level=result["risk_level"],
        risk_flags=json.dumps(result["flags"]),
        risk_explanation=json.dumps(result["explanations"]),
        scam_keywords_found=json.dumps(result["scam_keywords_found"]),
        vulnerable_user_mode=bool(data.get("vulnerable_user_mode", False)),
        status=TransactionStatus.HELD.value if result["risk_level"] == "HIGH" else TransactionStatus.PENDING.value,
    )

    # Check for trusted contact alert
    if result["should_alert_contact"]:
        contact = TrustedContact.query.filter_by(org_id=user.org_id, is_active=True).first()
        if contact and contact.consent_given:
            sent = send_trusted_contact_alert(
                contact.contact_name,
                contact.contact_email or "",
                contact.contact_phone or "",
                {**result, "amount": amount, "recipient_name": recipient_name}
            )
            txn.trusted_contact_alerted = sent
            txn.trusted_contact_name = contact.contact_name

    db.session.add(txn)
    db.session.commit()

    return jsonify({
        "transaction_id": txn.id,
        **result,
    }), 200


@shield_bp.route("/confirm/<int:txn_id>", methods=["POST"])
@auth_required
def confirm_transaction(txn_id):
    """User confirms a flagged transaction is legitimate."""
    user = get_current_user()
    txn = FraudTransaction.query.filter_by(id=txn_id, org_id=user.org_id).first_or_404()

    txn.status = TransactionStatus.CONFIRMED.value
    txn.resolved_at = datetime.utcnow()
    txn.user_feedback = "legit"
    db.session.commit()

    return jsonify({"message": "Transaction confirmed. System has learned from your feedback.", "status": "CONFIRMED"})


@shield_bp.route("/cancel/<int:txn_id>", methods=["POST"])
@auth_required
def cancel_transaction(txn_id):
    """User cancels a high-risk transaction."""
    user = get_current_user()
    txn = FraudTransaction.query.filter_by(id=txn_id, org_id=user.org_id).first_or_404()

    data = request.get_json(silent=True) or {}
    txn.status = TransactionStatus.CANCELLED.value
    txn.resolved_at = datetime.utcnow()
    txn.user_feedback = "fraud"
    db.session.commit()

    return jsonify({"message": "Transaction cancelled and reported. Thank you for keeping your account safe.", "status": "CANCELLED"})


@shield_bp.route("/history", methods=["GET"])
@auth_required
def history():
    """Get recent analyzed transactions."""
    user = get_current_user()
    limit = min(int(request.args.get("limit", 20)), 50)
    risk_filter = request.args.get("risk_level")

    query = FraudTransaction.query.filter_by(org_id=user.org_id)
    if risk_filter and risk_filter in ["LOW", "MEDIUM", "HIGH"]:
        query = query.filter_by(risk_level=risk_filter)

    transactions = query.order_by(FraudTransaction.created_at.desc()).limit(limit).all()
    return jsonify({"transactions": [t.to_dict() for t in transactions]})


@shield_bp.route("/stats", methods=["GET"])
@auth_required
def stats():
    """Get SmartShield dashboard statistics."""
    user = get_current_user()
    return jsonify(get_shield_stats(user.org_id))


@shield_bp.route("/trusted-contact", methods=["GET"])
@auth_required
def get_trusted_contact():
    """Get trusted contact info."""
    user = get_current_user()
    contact = TrustedContact.query.filter_by(org_id=user.org_id).first()
    if not contact:
        return jsonify({"contact": None})
    return jsonify({"contact": contact.to_dict()})


@shield_bp.route("/trusted-contact", methods=["POST"])
@auth_required
def set_trusted_contact():
    """Create or update trusted contact."""
    user = get_current_user()
    data = request.get_json(silent=True) or {}

    name = (data.get("contact_name") or "").strip()
    if not name:
        return jsonify({"error": "contact_name is required"}), 400

    contact = TrustedContact.query.filter_by(org_id=user.org_id).first()
    if contact:
        contact.contact_name = name
        contact.contact_phone = data.get("contact_phone", "").strip()
        contact.contact_email = data.get("contact_email", "").strip()
        contact.is_active = True
        contact.consent_given = bool(data.get("consent_given", True))
        contact.updated_at = datetime.utcnow()
    else:
        contact = TrustedContact(
            org_id=user.org_id,
            user_id=user.id,
            contact_name=name,
            contact_phone=data.get("contact_phone", "").strip(),
            contact_email=data.get("contact_email", "").strip(),
            consent_given=bool(data.get("consent_given", True)),
        )
        db.session.add(contact)

    db.session.commit()
    return jsonify({"message": "Trusted contact saved successfully.", "contact": contact.to_dict()}), 200


@shield_bp.route("/chatbot", methods=["POST"])
@auth_required
@limiter.limit("20 per minute")
def chatbot():
    """Fraud awareness chatbot."""
    user = get_current_user()
    data = request.get_json(silent=True) or {}
    query = (data.get("query") or "").strip()

    if not query:
        return jsonify({"error": "query is required"}), 400

    result = fraud_chatbot(query, user.org_id)

    # Log chatbot interaction
    report = ScamReport(
        org_id=user.org_id,
        user_id=user.id,
        query=query,
        response=result["response"],
        is_scam_detected=result["is_scam_detected"],
        scam_category=result.get("scam_category", ""),
    )
    db.session.add(report)
    db.session.commit()

    return jsonify(result)
