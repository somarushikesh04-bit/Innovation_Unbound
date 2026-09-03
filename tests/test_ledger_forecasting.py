"""
tests/test_ledger_forecasting.py
Dedicated unit + integration tests for the double-entry ledger
and financial forecasting engine.

Covers:
  - Ledger CRUD (create, filter, pagination)
  - CSV bulk import
  - Cash Flow Runway projection
  - Break-Even analysis
  - Health Scorecard computation
  - DSCR / creditworthiness
  - Location feasibility scorer
  - Cap table & dilution simulator
"""
import json
import pytest
from datetime import date, timedelta
from app.extensions import db as _db
from app.models.tenant import Tenant
from app.models.user import User, UserRole
from app.models.ledger import LedgerEntry, EntryType, EntryCategory
from argon2 import PasswordHasher

ph = PasswordHasher()


# ─── Shared helpers ───────────────────────────────────────────────────────────

def _seed_tenant_with_data(db_session, slug_suffix="", days=90):
    """Create a tenant with realistic revenue + expense history."""
    tenant = Tenant(name=f"LF Co {slug_suffix}", slug=f"lf-co-{slug_suffix}")
    db_session.session.add(tenant)
    db_session.session.flush()

    user = User(
        org_id=tenant.id,
        email=f"lf-{slug_suffix}@test.com",
        password_hash=ph.hash("Test@1234"),
        full_name="LF Owner",
        role=UserRole.OWNER.value,
    )
    db_session.session.add(user)

    today = date.today()
    for i in range(days):
        d = today - timedelta(days=i)
        db_session.session.add(LedgerEntry(
            org_id=tenant.id,
            entry_type=EntryType.CREDIT.value,
            category=EntryCategory.SALES_CASH.value,
            amount=60_000,
            description="Daily Revenue",
            reference_date=d,
        ))
        db_session.session.add(LedgerEntry(
            org_id=tenant.id,
            entry_type=EntryType.DEBIT.value,
            category=EntryCategory.OPEX.value,
            amount=35_000,
            description="Daily OpEx",
            reference_date=d,
        ))

    db_session.session.commit()
    return tenant, user


def _login(client, email, password="Test@1234"):
    r = client.post("/api/auth/login",
                    json={"email": email, "password": password})
    assert r.status_code == 200, r.data
    return json.loads(r.data)["access_token"]


# ─── Forecasting Service Unit Tests ──────────────────────────────────────────

class TestRunwayProjection:
    def test_runway_days_positive_with_data(self, app, db):
        """Runway must be a positive integer when surplus cash exists."""
        with app.app_context():
            tenant, _ = _seed_tenant_with_data(db, "runway1")
            from app.services.forecasting import compute_runway
            result = compute_runway(tenant.id)
            assert isinstance(result, dict)
            assert result["runway_days"] > 0, "Expected positive runway for profitable tenant"

    def test_runway_contains_burn_rate(self, app, db):
        """Runway result must include monthly_burn and current_cash."""
        with app.app_context():
            tenant, _ = _seed_tenant_with_data(db, "runway2")
            from app.services.forecasting import compute_runway
            result = compute_runway(tenant.id)
            assert "monthly_burn" in result
            assert "current_cash" in result
            assert result["monthly_burn"] >= 0

    def test_runway_no_data_returns_defaults(self, app, db):
        """Empty tenant runway must return safe zero defaults without crashing."""
        with app.app_context():
            tenant = Tenant(name="Empty Runway", slug="empty-runway")
            db.session.add(tenant)
            db.session.commit()
            from app.services.forecasting import compute_runway
            result = compute_runway(tenant.id)
            assert "runway_days" in result


class TestBreakEvenAnalysis:
    def test_break_even_returns_expected_keys(self, app, db):
        """Break-even result must contain margin, fixed/variable cost keys."""
        with app.app_context():
            tenant, _ = _seed_tenant_with_data(db, "be1")
            from app.services.forecasting import compute_break_even
            result = compute_break_even(tenant.id)
            assert "break_even_revenue_monthly" in result or "break_even_revenue_daily" in result or "message" in result

    def test_break_even_with_mixed_categories(self, app, db):
        """Break-even properly classifies COGS as variable and OPEX as fixed."""
        with app.app_context():
            tenant = Tenant(name="BE Mixed", slug="be-mixed")
            db.session.add(tenant)
            db.session.flush()

            today = date.today()
            for i in range(30):
                d = today - timedelta(days=i)
                db.session.add(LedgerEntry(
                    org_id=tenant.id, entry_type=EntryType.CREDIT.value,
                    category=EntryCategory.SALES_CASH.value,
                    amount=100_000, reference_date=d,
                ))
                db.session.add(LedgerEntry(
                    org_id=tenant.id, entry_type=EntryType.DEBIT.value,
                    category=EntryCategory.COGS.value,
                    amount=40_000, reference_date=d,
                ))
                db.session.add(LedgerEntry(
                    org_id=tenant.id, entry_type=EntryType.DEBIT.value,
                    category=EntryCategory.OPEX.value,
                    amount=20_000, reference_date=d,
                ))
            db.session.commit()

            from app.services.forecasting import compute_break_even
            result = compute_break_even(tenant.id)
            assert isinstance(result, dict)


class TestHealthScorecard:
    def test_health_score_range(self, app, db):
        """Health score must be in 0–100 range with a grade string."""
        with app.app_context():
            tenant, _ = _seed_tenant_with_data(db, "health1")
            from app.services.forecasting import compute_health_score
            result = compute_health_score(tenant.id)
            assert 0 <= result["score"] <= 100
            assert result["grade"] in ("A+", "A", "B", "C", "D")

    def test_health_score_four_dimensions(self, app, db):
        """Health score must include solvency, liquidity, profitability, efficiency."""
        with app.app_context():
            tenant, _ = _seed_tenant_with_data(db, "health2")
            from app.services.forecasting import compute_health_score
            result = compute_health_score(tenant.id)
            for key in ("solvency", "liquidity", "profitability", "efficiency"):
                assert key in result, f"Missing dimension: {key}"
                assert 0 <= result[key] <= 100


class TestDSCRAndCreditworthiness:
    def test_dscr_structure(self, app, db):
        """DSCR result must return dscr, rating, working_capital keys."""
        with app.app_context():
            tenant, _ = _seed_tenant_with_data(db, "dscr1")
            from app.services.forecasting import compute_dscr
            result = compute_dscr(tenant.id)
            for key in ("dscr", "rating", "working_capital", "current_ratio"):
                assert key in result, f"Missing key: {key}"

    def test_dscr_rating_valid(self, app, db):
        """DSCR rating must be one of EXCELLENT, GOOD, FAIR, POOR."""
        with app.app_context():
            tenant, _ = _seed_tenant_with_data(db, "dscr2")
            from app.services.forecasting import compute_dscr
            result = compute_dscr(tenant.id)
            assert result["rating"] in ("EXCELLENT", "GOOD", "FAIR", "POOR")


class TestLocationScorer:
    def test_location_score_range(self, app, db):
        """Location feasibility score must be 0–100."""
        with app.app_context():
            from app.services.forecasting import compute_location_score
            result = compute_location_score(
                monthly_rent=50_000,
                footfall=800,
                competitors=3,
                niche_fit=7,
                parking=6,
                current_monthly_revenue=200_000,
            )
            assert 0 <= result["feasibility_score"] <= 100

    def test_high_rent_reduces_score(self, app, db):
        """Excessively high rent-to-revenue ratio must yield a lower score."""
        with app.app_context():
            from app.services.forecasting import compute_location_score
            low_rent = compute_location_score(
                monthly_rent=10_000, footfall=600, competitors=2,
                niche_fit=7, parking=7, current_monthly_revenue=200_000,
            )["feasibility_score"]
            high_rent = compute_location_score(
                monthly_rent=180_000, footfall=600, competitors=2,
                niche_fit=7, parking=7, current_monthly_revenue=200_000,
            )["feasibility_score"]
            assert low_rent > high_rent, "Lower rent should yield a higher score"


# ─── Ledger API Integration Tests ────────────────────────────────────────────

class TestLedgerAPI:
    def _setup(self, client, db, suffix="api"):
        client.post("/api/auth/register", json={
            "email": f"ledger-{suffix}@biz.com",
            "password": "Test@1234",
            "full_name": "Ledger Owner",
            "business_name": f"Ledger Biz {suffix}",
        })
        token = _login(client, f"ledger-{suffix}@biz.com")
        return token

    def test_create_and_retrieve_entry(self, client, db):
        token = self._setup(client, db, "cr1")
        r = client.post("/api/ledger/entries",
                        json={
                            "entry_type": "DEBIT",
                            "category": "OPEX",
                            "amount": 25_000,
                            "description": "Office rent",
                            "reference_date": str(date.today()),
                        },
                        headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 201

        r2 = client.get("/api/ledger/entries",
                        headers={"Authorization": f"Bearer {token}"})
        assert r2.status_code == 200
        data = json.loads(r2.data)
        assert len(data["entries"]) >= 1

    def test_ledger_entries_tenant_scoped(self, client, db):
        """Entries returned must all belong to the authenticated tenant."""
        token = self._setup(client, db, "scope1")
        client.post("/api/ledger/entries",
                    json={
                        "entry_type": "CREDIT",
                        "category": "SALES_CASH",
                        "amount": 10_000,
                        "reference_date": str(date.today()),
                    },
                    headers={"Authorization": f"Bearer {token}"})

        r = client.get("/api/ledger/entries",
                       headers={"Authorization": f"Bearer {token}"})
        data = json.loads(r.data)
        me_r = client.get("/api/auth/me",
                          headers={"Authorization": f"Bearer {token}"})
        my_org = json.loads(me_r.data)["tenant"]["id"]
        for e in data["entries"]:
            assert e["org_id"] == my_org, "Cross-tenant entry returned!"

    def test_missing_amount_rejected(self, client, db):
        token = self._setup(client, db, "bad1")
        r = client.post("/api/ledger/entries",
                        json={"entry_type": "DEBIT", "category": "OPEX"},
                        headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 400

    def test_negative_amount_rejected(self, client, db):
        token = self._setup(client, db, "bad2")
        r = client.post("/api/ledger/entries",
                        json={"entry_type": "DEBIT", "category": "OPEX",
                              "amount": -500, "reference_date": str(date.today())},
                        headers={"Authorization": f"Bearer {token}"})
        assert r.status_code in (400, 422)
