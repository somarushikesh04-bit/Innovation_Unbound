"""
app/utils/security.py
Security hardening utilities:
  - CSP configuration for Flask-Talisman
  - Composite DB index definitions (already declared in model __table_args__)
  - In-process health score caching with TTL (avoids repeated heavy aggregations)
  - IDOR guard helper
"""
import time
from typing import Optional
from flask import g, jsonify, abort
from flask_jwt_extended import get_jwt_identity


# ── CSP Policy for Flask-Talisman ─────────────────────────────────────────────
CSP_POLICY = {
    "default-src": "'self'",
    "script-src": [
        "'self'",
        "https://cdn.jsdelivr.net",        # Chart.js CDN
        "'unsafe-inline'",                 # Inline event handlers in index.html
    ],
    "style-src": [
        "'self'",
        "https://fonts.googleapis.com",
        "'unsafe-inline'",
    ],
    "font-src": [
        "'self'",
        "https://fonts.gstatic.com",
        "https://fonts.googleapis.com",
    ],
    "img-src": ["'self'", "data:", "blob:"],
    "connect-src": [
        "'self'",
        "https://generativelanguage.googleapis.com",  # Gemini API
    ],
    "frame-ancestors": "'none'",
    "form-action": "'self'",
    "base-uri": "'self'",
    "object-src": "'none'",
}

# ── In-Process Health Score Cache (simple TTL dict) ───────────────────────────
# Keyed by org_id → { "data": {...}, "expires_at": float }
_health_cache: dict = {}
HEALTH_CACHE_TTL = 300  # 5 minutes


def get_cached_health(org_id: int) -> Optional[dict]:
    """Return cached health data if still valid."""
    entry = _health_cache.get(org_id)
    if entry and time.time() < entry["expires_at"]:
        return entry["data"]
    return None


def set_cached_health(org_id: int, data: dict) -> None:
    """Store health computation in cache."""
    _health_cache[org_id] = {
        "data": data,
        "expires_at": time.time() + HEALTH_CACHE_TTL,
    }


def invalidate_health_cache(org_id: int) -> None:
    """Invalidate cached health on new ledger entries."""
    _health_cache.pop(org_id, None)


# ── IDOR / BOLA Guard ─────────────────────────────────────────────────────────
def assert_tenant_owns(resource_org_id: int, current_org_id: int, label: str = "resource") -> None:
    """
    Abort with 404 if the resource does not belong to the current tenant.
    Using 404 instead of 403 to avoid leaking existence of cross-tenant data.
    """
    if resource_org_id != current_org_id:
        abort(404, description=f"{label} not found")


# ── Audit Log Helper ──────────────────────────────────────────────────────────
def write_audit(db, org_id: int, user_id: int, action: str,
                resource_type: str = "", resource_id: int = None,
                ip_address: str = None, extra: dict = None):
    """Write an audit log entry.  Silently fails — never blocks request flow."""
    try:
        from app.models.audit import AuditLog
        import json
        log = AuditLog(
            org_id=org_id,
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            ip_address=ip_address,
            metadata_json=json.dumps(extra or {}),
        )
        db.session.add(log)
        # Committed by the caller's existing session flush
    except Exception:
        pass  # Audit failures must never break application flow


# ── Health Snapshot Persistence ───────────────────────────────────────────────
def save_health_snapshot(db, org_id: int, health_data: dict) -> None:
    """Persist a health score snapshot for trend analysis.  Non-blocking."""
    try:
        from app.models.health_score import HealthScoreSnapshot
        snap = HealthScoreSnapshot(
            org_id=org_id,
            score=health_data.get("score", 0),
            grade=health_data.get("grade", "—"),
            solvency=health_data.get("solvency", 0),
            liquidity=health_data.get("liquidity", 0),
            profitability=health_data.get("profitability", 0),
            efficiency=health_data.get("efficiency", 0),
            runway_days=health_data.get("runway_days", 0),
            monthly_burn=health_data.get("monthly_burn", 0),
        )
        db.session.add(snap)
    except Exception:
        pass
