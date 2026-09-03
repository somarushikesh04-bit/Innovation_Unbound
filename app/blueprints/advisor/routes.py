from flask import Blueprint, request, jsonify
from app.extensions import db, limiter
from app.utils.decorators import auth_required, role_required, get_current_user
from app.models.user import UserRole
from app.services.advisor_service import ask_advisor, QUICK_INSIGHTS, build_financial_context

advisor_bp = Blueprint("advisor", __name__, url_prefix="/api/advisor")


def _advisor_rate_key():
    try:
        user = get_current_user()
        return str(user.id) if user else "anon"
    except Exception:
        return "anon"


@advisor_bp.route("/chat", methods=["POST"])
@limiter.limit("20 per hour", key_func=_advisor_rate_key)
@role_required(UserRole.ACCOUNTANT, UserRole.OWNER)
def chat():

    user = get_current_user()
    data = request.get_json(silent=True) or {}
    question = str(data.get("question") or data.get("message") or "").strip()

    if not question:
        return jsonify({"error": "A question is required"}), 400
    if len(question) > 500:
        return jsonify({"error": "Question too long (max 500 characters)"}), 400

    result = ask_advisor(question, user.org_id)
    return jsonify({
        "question": question,
        "answer": result["answer"],
        "source": result["source"],
        "grounded": result.get("context_used", False),
    })


@advisor_bp.route("/quick-insights", methods=["GET"])
@auth_required
def quick_insights():
    return jsonify({"insights": QUICK_INSIGHTS})


@advisor_bp.route("/context", methods=["GET"])
@role_required(UserRole.ACCOUNTANT, UserRole.OWNER)
def get_context():
    user = get_current_user()
    ctx = build_financial_context(user.org_id)
    return jsonify({"context": ctx})
