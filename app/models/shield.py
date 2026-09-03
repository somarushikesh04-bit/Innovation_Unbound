"""
app/models/shield.py
SmartShield — AI Banking Fraud Protection Models
"""
from app.extensions import db
from datetime import datetime
import enum


class RiskLevel(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class TransactionStatus(str, enum.Enum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"
    HELD = "HELD"


class PaymentMethod(str, enum.Enum):
    UPI = "UPI"
    NEFT = "NEFT"
    IMPS = "IMPS"
    RTGS = "RTGS"
    CARD = "CARD"
    CASH = "CASH"
    OTHER = "OTHER"


class FraudTransaction(db.Model):
    """Stores each analyzed transaction with its risk assessment."""
    __tablename__ = "shield_transactions"
    __table_args__ = (
        db.Index("ix_shield_org_created", "org_id", "created_at"),
        db.Index("ix_shield_org_risk", "org_id", "risk_level"),
    )

    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey("tenants.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    # Transaction details
    amount = db.Column(db.Float, nullable=False)
    recipient_name = db.Column(db.String(200), nullable=False)
    recipient_id = db.Column(db.String(200))        # UPI ID / account number
    payment_method = db.Column(db.String(20), default=PaymentMethod.UPI.value)
    description = db.Column(db.String(500))          # transaction remark/narration
    device_id = db.Column(db.String(100))
    location = db.Column(db.String(100))
    transaction_hour = db.Column(db.Integer)         # 0–23

    # Risk assessment
    risk_score = db.Column(db.Integer, nullable=False, default=0)  # 0–100
    risk_level = db.Column(db.String(10), nullable=False, default=RiskLevel.LOW.value)
    risk_flags = db.Column(db.Text, default="[]")    # JSON list of flag strings
    risk_explanation = db.Column(db.Text, default="[]")  # JSON list of human explanations
    scam_keywords_found = db.Column(db.Text, default="[]")  # JSON list

    # Vulnerable user mode flag
    vulnerable_user_mode = db.Column(db.Boolean, default=False)

    # Trusted contact alert sent?
    trusted_contact_alerted = db.Column(db.Boolean, default=False)
    trusted_contact_name = db.Column(db.String(200))

    # Resolution
    status = db.Column(db.String(20), default=TransactionStatus.PENDING.value)
    resolved_at = db.Column(db.DateTime)
    user_feedback = db.Column(db.String(50))  # "legit" / "fraud"

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        import json
        return {
            "id": self.id,
            "org_id": self.org_id,
            "amount": self.amount,
            "recipient_name": self.recipient_name,
            "recipient_id": self.recipient_id,
            "payment_method": self.payment_method,
            "description": self.description,
            "device_id": self.device_id,
            "location": self.location,
            "transaction_hour": self.transaction_hour,
            "risk_score": self.risk_score,
            "risk_level": self.risk_level,
            "risk_flags": json.loads(self.risk_flags or "[]"),
            "risk_explanation": json.loads(self.risk_explanation or "[]"),
            "scam_keywords_found": json.loads(self.scam_keywords_found or "[]"),
            "vulnerable_user_mode": self.vulnerable_user_mode,
            "trusted_contact_alerted": self.trusted_contact_alerted,
            "trusted_contact_name": self.trusted_contact_name,
            "status": self.status,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "user_feedback": self.user_feedback,
            "created_at": self.created_at.isoformat(),
        }


class TrustedContact(db.Model):
    """Guardian/trusted family member who receives high-risk alerts."""
    __tablename__ = "shield_trusted_contacts"

    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey("tenants.id"), nullable=False, unique=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    contact_name = db.Column(db.String(200), nullable=False)
    contact_phone = db.Column(db.String(20))
    contact_email = db.Column(db.String(255))
    is_active = db.Column(db.Boolean, default=True)
    consent_given = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "contact_name": self.contact_name,
            "contact_phone": self.contact_phone,
            "contact_email": self.contact_email,
            "is_active": self.is_active,
            "consent_given": self.consent_given,
        }


class ScamReport(db.Model):
    """Records fraud chatbot queries and system responses."""
    __tablename__ = "shield_scam_reports"

    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey("tenants.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    query = db.Column(db.Text, nullable=False)
    response = db.Column(db.Text)
    is_scam_detected = db.Column(db.Boolean, default=False)
    scam_category = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "query": self.query,
            "response": self.response,
            "is_scam_detected": self.is_scam_detected,
            "scam_category": self.scam_category,
            "created_at": self.created_at.isoformat(),
        }
