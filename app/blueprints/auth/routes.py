from flask import Blueprint, request, jsonify, make_response
from flask_jwt_extended import (
    create_access_token, create_refresh_token,
    jwt_required, get_jwt_identity, set_access_cookies,
    set_refresh_cookies, unset_jwt_cookies
)
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
import re

from app.extensions import db, limiter
from app.models.tenant import Tenant
from app.models.user import User, UserRole
from app.models.audit import AuditLog
from app.utils.decorators import get_current_user, auth_required

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")
ph = PasswordHasher(time_cost=2, memory_cost=65536, parallelism=2)

EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")


@auth_bp.route("/register", methods=["POST"])
@limiter.limit("60 per minute")
def register():
    data = request.get_json(silent=True) or {}
    required = ["email", "password", "full_name", "business_name"]
    for field in required:
        if not data.get(field):
            return jsonify({"error": f"Field '{field}' is required"}), 400

    email = data["email"].strip().lower()
    if not EMAIL_RE.match(email):
        return jsonify({"error": "Invalid email address"}), 400

    if len(data["password"]) < 8:
        return jsonify({"error": "Password must be at least 8 characters"}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({"error": "An account with this email already exists"}), 409

    # Create tenant
    slug = re.sub(r"[^a-z0-9]+", "-", data["business_name"].strip().lower())[:50]
    base_slug = slug
    counter = 1
    while Tenant.query.filter_by(slug=slug).first():
        slug = f"{base_slug}-{counter}"
        counter += 1

    tenant = Tenant(name=data["business_name"].strip(), slug=slug)
    db.session.add(tenant)
    db.session.flush()

    # Create owner user
    user = User(
        org_id=tenant.id,
        email=email,
        password_hash=ph.hash(data["password"]),
        full_name=data["full_name"].strip(),
        role=UserRole.OWNER.value,
    )
    db.session.add(user)
    db.session.commit()

    access_token = create_access_token(identity=str(user.id))
    refresh_token = create_refresh_token(identity=str(user.id))

    resp = make_response(jsonify({
        "message": "Account created successfully",
        "user": user.to_dict(),
        "tenant": tenant.to_dict(),
        "access_token": access_token,
    }), 201)
    set_access_cookies(resp, access_token)
    set_refresh_cookies(resp, refresh_token)
    return resp


@auth_bp.route("/login", methods=["POST"])
@limiter.limit("60 per minute")
def login():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not email or not password:
        return jsonify({"error": "Email and password required"}), 400

    user = User.query.filter_by(email=email).first()
    if not user or not user.is_active:
        return jsonify({"error": "Invalid credentials"}), 401

    try:
        ph.verify(user.password_hash, password)
    except VerifyMismatchError:
        return jsonify({"error": "Invalid credentials"}), 401

    # Rehash if needed
    if ph.check_needs_rehash(user.password_hash):
        user.password_hash = ph.hash(password)
        db.session.commit()

    tenant = db.session.get(Tenant, user.org_id)
    access_token = create_access_token(identity=str(user.id))
    refresh_token = create_refresh_token(identity=str(user.id))

    # Audit log
    audit = AuditLog(org_id=user.org_id, user_id=user.id,
                     action="USER_LOGIN", resource_type="User",
                     ip_address=request.remote_addr)
    db.session.add(audit)
    db.session.commit()

    resp = make_response(jsonify({
        "message": "Login successful",
        "user": user.to_dict(),
        "tenant": tenant.to_dict() if tenant else {},
        "access_token": access_token,
    }))
    set_access_cookies(resp, access_token)
    set_refresh_cookies(resp, refresh_token)
    return resp


@auth_bp.route("/refresh", methods=["POST"])
@jwt_required(refresh=True)
def refresh():
    user_id = get_jwt_identity()
    access_token = create_access_token(identity=user_id)
    resp = make_response(jsonify({"message": "Token refreshed"}))
    set_access_cookies(resp, access_token)
    return resp


@auth_bp.route("/logout", methods=["POST"])
def logout():
    resp = make_response(jsonify({"message": "Logged out successfully"}))
    unset_jwt_cookies(resp)
    return resp


@auth_bp.route("/me", methods=["GET"])
@auth_required
def me():
    user = get_current_user()
    tenant = db.session.get(Tenant, user.org_id)
    return jsonify({
        "user": user.to_dict(),
        "tenant": tenant.to_dict() if tenant else {},
        "permissions": user.permissions,
    })


@auth_bp.route("/invite", methods=["POST"])
@auth_required
def invite_user():
    current = get_current_user()
    if current.role not in [UserRole.OWNER.value, UserRole.SUPERADMIN.value]:
        return jsonify({"error": "Only owners can invite users"}), 403

    data = request.get_json(silent=True) or {}
    required = ["email", "full_name", "role"]
    for field in required:
        if not data.get(field):
            return jsonify({"error": f"Field '{field}' is required"}), 400

    valid_roles = [r.value for r in UserRole if r != UserRole.SUPERADMIN]
    if data["role"] not in valid_roles:
        return jsonify({"error": f"Invalid role. Choose from: {valid_roles}"}), 400

    email = data["email"].strip().lower()
    if User.query.filter_by(email=email).first():
        return jsonify({"error": "User with this email already exists"}), 409

    import secrets
    temp_password = f"Msme360!{secrets.token_urlsafe(9)}"
    new_user = User(
        org_id=current.org_id,
        email=email,
        password_hash=ph.hash(temp_password),
        full_name=data["full_name"].strip(),
        role=data["role"],
    )
    db.session.add(new_user)
    db.session.commit()

    return jsonify({
        "message": f"User invited. Temporary password: {temp_password}",
        "user": new_user.to_dict(),
    }), 201
