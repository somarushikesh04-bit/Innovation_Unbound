from app.extensions import db
from datetime import datetime
import enum


class EntryType(str, enum.Enum):
    DEBIT = "DEBIT"
    CREDIT = "CREDIT"


class EntryCategory(str, enum.Enum):
    SALES_CASH = "SALES_CASH"
    SALES_CREDIT = "SALES_CREDIT"
    OPEX = "OPEX"
    COGS = "COGS"
    INVENTORY = "INVENTORY"
    LIABILITY = "LIABILITY"
    RECEIVABLE = "RECEIVABLE"
    OTHER = "OTHER"


class LedgerEntry(db.Model):
    __tablename__ = "ledger_entries"
    __table_args__ = (
        db.Index("ix_ledger_org_created", "org_id", "created_at"),
        db.Index("ix_ledger_org_category", "org_id", "category"),
    )

    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey("tenants.id"), nullable=False)
    entry_type = db.Column(db.String(10), nullable=False)
    category = db.Column(db.String(30), nullable=False, default=EntryCategory.OTHER.value)
    amount = db.Column(db.Float, nullable=False)
    description = db.Column(db.String(500))
    party_name = db.Column(db.String(200))
    reference_date = db.Column(db.Date, nullable=False, default=datetime.utcnow)
    metadata_json = db.Column(db.Text, default="{}")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"))

    tenant = db.relationship("Tenant", back_populates="ledger_entries")

    def to_dict(self):
        return {
            "id": self.id,
            "org_id": self.org_id,
            "entry_type": self.entry_type,
            "category": self.category,
            "amount": self.amount,
            "description": self.description,
            "party_name": self.party_name,
            "reference_date": self.reference_date.isoformat() if self.reference_date else None,
            "created_at": self.created_at.isoformat(),
        }
