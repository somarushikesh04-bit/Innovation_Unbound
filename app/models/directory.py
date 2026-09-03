from app.extensions import db
from datetime import datetime


class CustomerSupplier(db.Model):
    __tablename__ = "customer_suppliers"
    __table_args__ = (
        db.Index("ix_cs_org_type", "org_id", "entity_type"),
    )

    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey("tenants.id"), nullable=False)
    entity_type = db.Column(db.String(10), nullable=False)  # CUSTOMER / SUPPLIER
    name = db.Column(db.String(200), nullable=False)
    gstin = db.Column(db.String(20))
    phone = db.Column(db.String(20))
    email = db.Column(db.String(255))
    payment_terms_days = db.Column(db.Integer, default=30)
    outstanding_balance = db.Column(db.Float, default=0.0)
    settlement_speed_score = db.Column(db.Float, default=5.0)  # 1-10
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    tenant = db.relationship("Tenant", back_populates="contacts")

    def to_dict(self):
        return {
            "id": self.id,
            "entity_type": self.entity_type,
            "name": self.name,
            "gstin": self.gstin,
            "phone": self.phone,
            "email": self.email,
            "payment_terms_days": self.payment_terms_days,
            "outstanding_balance": self.outstanding_balance,
            "settlement_speed_score": self.settlement_speed_score,
        }


class InventoryItem(db.Model):
    __tablename__ = "inventory_items"
    __table_args__ = (
        db.Index("ix_inv_org", "org_id"),
    )

    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey("tenants.id"), nullable=False)
    sku = db.Column(db.String(100))
    name = db.Column(db.String(200), nullable=False)
    unit_volume = db.Column(db.Integer, default=0)
    unit_cost = db.Column(db.Float, default=0.0)
    selling_price = db.Column(db.Float, default=0.0)
    turnover_frequency_days = db.Column(db.Float, default=30.0)
    reorder_threshold = db.Column(db.Integer, default=10)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    tenant = db.relationship("Tenant", back_populates="inventory_items")

    @property
    def is_low_stock(self):
        return self.unit_volume <= self.reorder_threshold

    @property
    def cogs(self):
        return self.unit_cost * self.unit_volume

    def to_dict(self):
        return {
            "id": self.id,
            "sku": self.sku,
            "name": self.name,
            "unit_volume": self.unit_volume,
            "unit_cost": self.unit_cost,
            "selling_price": self.selling_price,
            "turnover_frequency_days": self.turnover_frequency_days,
            "reorder_threshold": self.reorder_threshold,
            "is_low_stock": self.is_low_stock,
            "cogs": self.cogs,
        }
