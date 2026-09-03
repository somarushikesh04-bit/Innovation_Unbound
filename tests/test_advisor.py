"""
tests/test_advisor.py
Unit tests for the AI Business Advisor service:
  - Quick insights generation
  - Financial context builder
  - Rule-based fallback answers (no Gemini key required)
  - Grounded prompt validation
"""
import json
import uuid
import pytest
from app.extensions import db as _db
from app.models.tenant import Tenant
from app.models.user import User, UserRole
from app.models.ledger import LedgerEntry, EntryType, EntryCategory
from argon2 import PasswordHasher
from datetime import date, timedelta

ph = PasswordHasher()


def _make_tenant_with_data(db_session):
    """Create a tenant with 30 days of sample ledger data."""
    uid = uuid.uuid4().hex[:8]
    tenant = Tenant(name=f"Advisor Co {uid}", slug=f"advisor-co-{uid}")
    db_session.session.add(tenant)
    db_session.session.flush()

    user = User(
        org_id=tenant.id,
        email=f"advisor-owner-{uid}@test.com",
        password_hash=ph.hash("Test@1234"),
        full_name="Advisor Owner",
        role=UserRole.OWNER.value,
    )
    db_session.session.add(user)

    # Seed 30 days of ledger entries
    today = date.today()
    for i in range(30):
        d = today - timedelta(days=i)
        db_session.session.add(LedgerEntry(
            org_id=tenant.id,
            entry_type=EntryType.CREDIT.value,
            category=EntryCategory.SALES_CASH.value,
            amount=50000,
            reference_date=d,
        ))
        db_session.session.add(LedgerEntry(
            org_id=tenant.id,
            entry_type=EntryType.DEBIT.value,
            category=EntryCategory.OPEX.value,
            amount=30000,
            reference_date=d,
        ))

    db_session.session.commit()
    return tenant, user


class TestAdvisorService:
    """Tests for the advisor_service module functions."""

    def test_quick_insights_list_nonempty(self, app, db):
        """QUICK_INSIGHTS constant must be a non-empty list of strings."""
        with app.app_context():
            from app.services.advisor_service import QUICK_INSIGHTS
            assert isinstance(QUICK_INSIGHTS, list), "QUICK_INSIGHTS must be a list"
            assert len(QUICK_INSIGHTS) >= 4, "At least 4 quick insight prompts expected"
            for item in QUICK_INSIGHTS:
                assert isinstance(item, str) and len(item) > 5

    def test_build_financial_context_structure(self, app, db):
        """build_financial_context must return non-empty context with revenue/expense data."""
        with app.app_context():
            tenant, _ = _make_tenant_with_data(db)
            from app.services.advisor_service import build_financial_context
            ctx = build_financial_context(tenant.id)
            # Returns either a dict or a formatted string — both are valid
            assert ctx, "Context must not be empty"
            ctx_str = json.dumps(ctx) if isinstance(ctx, dict) else str(ctx)
            ctx_str = ctx_str.lower()
            assert any(k in ctx_str for k in ("revenue", "income", "sales")), \
                "Context must include revenue data"
            assert any(k in ctx_str for k in ("expense", "opex", "burn", "cost")), \
                "Context must include expense data"

    def test_ask_advisor_returns_answer(self, app, db):
        """ask_advisor must always return a dict with 'answer' and 'source' keys."""
        with app.app_context():
            tenant, _ = _make_tenant_with_data(db)
            from app.services.advisor_service import ask_advisor
            result = ask_advisor("What is my current cash burn rate?", tenant.id)
            assert isinstance(result, dict), "Result must be a dict"
            assert "answer" in result, "'answer' key missing"
            assert "source" in result, "'source' key missing"
            assert len(result["answer"]) > 10, "Answer must be a non-trivial string"

    def test_ask_advisor_grounded_in_context(self, app, db):
        """Advisor must acknowledge grounding (context_used flag or numeric data)."""
        with app.app_context():
            tenant, _ = _make_tenant_with_data(db)
            from app.services.advisor_service import ask_advisor
            result = ask_advisor("Can I afford to hire a new employee?", tenant.id)
            # Either context_used is True or the answer contains numeric financial data
            answer_has_numbers = any(c.isdigit() for c in result["answer"])
            assert result.get("context_used") or answer_has_numbers, \
                "Advisor response must be grounded in financial data"

    def test_ask_advisor_never_crashes_on_empty_org(self, app, db):
        """Advisor must not throw an exception for a tenant with zero ledger data."""
        with app.app_context():
            tenant = Tenant(name="Empty Co", slug="empty-co-adv")
            db.session.add(tenant)
            db.session.commit()
            from app.services.advisor_service import ask_advisor
            result = ask_advisor("Where should I cut costs?", tenant.id)
            assert "answer" in result


class TestAdvisorEndpoints:
    """Integration tests for /api/advisor/* HTTP endpoints."""

    def _register_and_login(self, client):
        client.post("/api/auth/register", json={
            "email": "advtest@biz.com",
            "password": "Test@1234!",
            "full_name": "Adv Tester",
            "business_name": "Adv Biz",
        })
        r = client.post("/api/auth/login", json={
            "email": "advtest@biz.com",
            "password": "Test@1234!",
        })
        return json.loads(r.data).get("access_token", "")

    def test_quick_insights_endpoint(self, client, db):
        """GET /api/advisor/quick-insights returns 200 with insights list."""
        token = self._register_and_login(client)
        r = client.get("/api/advisor/quick-insights",
                       headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        data = json.loads(r.data)
        assert "insights" in data
        assert len(data["insights"]) >= 4

    def test_chat_requires_question(self, client, db):
        """POST /api/advisor/chat without a question returns 400."""
        token = self._register_and_login(client)
        r = client.post("/api/advisor/chat",
                        json={},
                        headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 400

    def test_chat_returns_answer(self, client, db):
        """POST /api/advisor/chat with valid question returns 200 with answer."""
        token = self._register_and_login(client)
        r = client.post("/api/advisor/chat",
                        json={"question": "What is my cash runway?"},
                        headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        data = json.loads(r.data)
        assert "answer" in data
        assert len(data["answer"]) > 5

    def test_chat_rejects_too_long_question(self, client, db):
        """POST /api/advisor/chat with >500 char question returns 400."""
        token = self._register_and_login(client)
        r = client.post("/api/advisor/chat",
                        json={"question": "A" * 501},
                        headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 400

    def test_unauthenticated_chat_rejected(self, client, db):
        """POST /api/advisor/chat without auth returns 401."""
        r = client.post("/api/advisor/chat",
                        json={"question": "What is my profit?"})
        assert r.status_code == 401
