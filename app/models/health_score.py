"""
HealthScoreSnapshot model — persists periodic health score snapshots for trend analysis.
"""
from app.extensions import db
from datetime import datetime


class HealthScoreSnapshot(db.Model):
    __tablename__ = "health_score_snapshots"
    __table_args__ = (
        db.Index("ix_health_org_recorded", "org_id", "recorded_at"),
    )

    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey("tenants.id"), nullable=False)

    score = db.Column(db.Float, nullable=False)  # 0-100
    grade = db.Column(db.String(3))              # A+, A, B, C, D
    solvency = db.Column(db.Float, default=0.0)
    liquidity = db.Column(db.Float, default=0.0)
    profitability = db.Column(db.Float, default=0.0)
    efficiency = db.Column(db.Float, default=0.0)
    runway_days = db.Column(db.Integer, default=0)
    monthly_burn = db.Column(db.Float, default=0.0)
    recorded_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    tenant = db.relationship("Tenant", backref=db.backref("health_snapshots", lazy="dynamic"))

    def to_dict(self):
        return {
            "id": self.id,
            "score": self.score,
            "grade": self.grade,
            "solvency": self.solvency,
            "liquidity": self.liquidity,
            "profitability": self.profitability,
            "efficiency": self.efficiency,
            "runway_days": self.runway_days,
            "monthly_burn": self.monthly_burn,
            "recorded_at": self.recorded_at.isoformat(),
        }
