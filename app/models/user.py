from app.extensions import db
from datetime import datetime
import enum


class UserRole(str, enum.Enum):
    VIEWER = "VIEWER"
    STAFF = "STAFF"
    ACCOUNTANT = "ACCOUNTANT"
    OWNER = "OWNER"
    SUPERADMIN = "SUPERADMIN"


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey("tenants.id"), nullable=False, index=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(512), nullable=False)
    full_name = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), nullable=False, default=UserRole.OWNER.value)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    tenant = db.relationship("Tenant", back_populates="users")

    def to_dict(self):
        return {
            "id": self.id,
            "org_id": self.org_id,
            "email": self.email,
            "full_name": self.full_name,
            "role": self.role,
            "is_active": self.is_active,
        }

    @property
    def permissions(self):
        role_perms = {
            UserRole.VIEWER.value: ["view_summaries"],
            UserRole.STAFF.value: ["view_summaries", "create_entries", "upload_invoices"],
            UserRole.ACCOUNTANT.value: [
                "view_summaries", "create_entries", "upload_invoices",
                "verify_invoices", "view_ledger", "adjust_balances", "view_audit"
            ],
            UserRole.OWNER.value: [
                "view_summaries", "create_entries", "upload_invoices",
                "verify_invoices", "view_ledger", "adjust_balances", "view_audit",
                "view_forecasts", "view_cap_table", "manage_cap_table",
                "view_financing", "invite_users", "use_ai_advisor"
            ],
            UserRole.SUPERADMIN.value: ["*"],
        }
        return role_perms.get(self.role, [])
