from app.extensions import db
from datetime import datetime


class Tenant(db.Model):
    __tablename__ = "tenants"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(100), unique=True, nullable=False, index=True)
    currency = db.Column(db.String(10), default="INR")
    settings_json = db.Column(db.Text, default="{}")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    users = db.relationship("User", back_populates="tenant", lazy="dynamic")
    ledger_entries = db.relationship("LedgerEntry", back_populates="tenant", lazy="dynamic")
    invoices = db.relationship("Invoice", back_populates="tenant", lazy="dynamic")
    inventory_items = db.relationship("InventoryItem", back_populates="tenant", lazy="dynamic")
    contacts = db.relationship("CustomerSupplier", back_populates="tenant", lazy="dynamic")
    cap_table_entries = db.relationship("CapTableEntry", back_populates="tenant", lazy="dynamic")

    def to_dict(self):
        return {"id": self.id, "name": self.name, "slug": self.slug, "currency": self.currency}
