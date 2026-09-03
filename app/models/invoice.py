from app.extensions import db
from datetime import datetime


class Invoice(db.Model):
    __tablename__ = "invoices"
    __table_args__ = (
        db.Index("ix_invoice_org_status", "org_id", "status"),
        db.Index("ix_invoice_org_created", "org_id", "created_at"),
    )

    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey("tenants.id"), nullable=False)
    invoice_number = db.Column(db.String(100))
    vendor_name = db.Column(db.String(200))
    vendor_gstin = db.Column(db.String(20))
    invoice_date = db.Column(db.Date)
    subtotal = db.Column(db.Float, default=0.0)
    tax_amount = db.Column(db.Float, default=0.0)
    total_amount = db.Column(db.Float, default=0.0)
    status = db.Column(db.String(20), default="PENDING")  # PENDING, VERIFIED, FLAGGED
    anomaly_flags_json = db.Column(db.Text, default="[]")
    file_path = db.Column(db.String(500))
    file_original_name = db.Column(db.String(255))
    line_items_json = db.Column(db.Text, default="[]")
    raw_ocr_text = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    verified_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    verified_at = db.Column(db.DateTime, nullable=True)

    tenant = db.relationship("Tenant", back_populates="invoices")

    def to_dict(self):
        import json
        return {
            "id": self.id,
            "invoice_number": self.invoice_number,
            "vendor_name": self.vendor_name,
            "vendor_gstin": self.vendor_gstin,
            "invoice_date": self.invoice_date.isoformat() if self.invoice_date else None,
            "subtotal": self.subtotal,
            "tax_amount": self.tax_amount,
            "total_amount": self.total_amount,
            "status": self.status,
            "anomaly_flags": json.loads(self.anomaly_flags_json or "[]"),
            "line_items": json.loads(self.line_items_json or "[]"),
            "file_original_name": self.file_original_name,
            "created_at": self.created_at.isoformat(),
        }


class CapTableEntry(db.Model):
    __tablename__ = "cap_table_entries"

    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey("tenants.id"), nullable=False)
    stakeholder_name = db.Column(db.String(200), nullable=False)
    stakeholder_type = db.Column(db.String(20), nullable=False)  # FOUNDER, INVESTOR, POOL
    equity_percentage = db.Column(db.Float, default=0.0)
    shares_count = db.Column(db.Integer, default=0)
    invested_amount = db.Column(db.Float, default=0.0)
    round_name = db.Column(db.String(100), default="Seed")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    tenant = db.relationship("Tenant", back_populates="cap_table_entries")

    def to_dict(self):
        return {
            "id": self.id,
            "stakeholder_name": self.stakeholder_name,
            "stakeholder_type": self.stakeholder_type,
            "equity_percentage": self.equity_percentage,
            "shares_count": self.shares_count,
            "invested_amount": self.invested_amount,
            "round_name": self.round_name,
        }


class LocationEvaluation(db.Model):
    __tablename__ = "location_evaluations"

    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey("tenants.id"), nullable=False)
    location_name = db.Column(db.String(200), nullable=False)
    monthly_rent = db.Column(db.Float, default=0.0)
    footfall_estimate = db.Column(db.Integer, default=0)
    competitor_count = db.Column(db.Integer, default=0)
    niche_fit_score = db.Column(db.Float, default=5.0)  # 1-10
    parking_access_score = db.Column(db.Float, default=5.0)  # 1-10
    feasibility_score = db.Column(db.Float, default=0.0)  # 0-100
    notes = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "location_name": self.location_name,
            "monthly_rent": self.monthly_rent,
            "footfall_estimate": self.footfall_estimate,
            "competitor_count": self.competitor_count,
            "niche_fit_score": self.niche_fit_score,
            "parking_access_score": self.parking_access_score,
            "feasibility_score": self.feasibility_score,
            "notes": self.notes,
        }
