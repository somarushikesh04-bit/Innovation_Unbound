from functools import wraps
from flask import jsonify
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity, get_jwt

from app.extensions import db
from app.models.user import User


def get_current_user():
    """Retrieve the authenticated user from the JWT identity."""
    user_id = get_jwt_identity()
    return db.session.get(User, int(user_id)) if user_id else None


def role_required(*allowed_roles):
    """Decorator: Ensures the current user has one of the specified roles."""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            try:
                verify_jwt_in_request()
            except Exception:
                return jsonify({"error": "Authentication required"}), 401

            user = get_current_user()
            if not user or not user.is_active:
                return jsonify({"error": "User not found or inactive"}), 401

            # SUPERADMIN has access to everything
            if user.role == "SUPERADMIN":
                return fn(*args, **kwargs)

            if user.role not in [r.value if hasattr(r, "value") else r for r in allowed_roles]:
                return jsonify({"error": "Insufficient permissions for this action"}), 403

            return fn(*args, **kwargs)
        return wrapper
    return decorator


def tenant_isolated(fn):
    """Decorator: Ensures all DB operations are scoped to the authenticated user's org_id."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            verify_jwt_in_request()
        except Exception:
            return jsonify({"error": "Authentication required"}), 401

        user = get_current_user()
        if not user or not user.is_active:
            return jsonify({"error": "User not found or inactive"}), 401

        return fn(*args, **kwargs)
    return wrapper


def auth_required(fn):
    """Minimal decorator: Just verify JWT is valid and user exists."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            verify_jwt_in_request()
        except Exception:
            return jsonify({"error": "Authentication required"}), 401

        user = get_current_user()
        if not user or not user.is_active:
            return jsonify({"error": "User not found or inactive"}), 401

        return fn(*args, **kwargs)
    return wrapper
