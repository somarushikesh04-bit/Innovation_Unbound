import pytest
from datetime import date, timedelta
from app.services.fraud_detector import (
    _check_math_discrepancy, _check_gstin, _check_spend_spike, _check_duplicate
)
from app.models.invoice import Invoice


class TestFraudDetector:
    def test_tax_math_discrepancy_detected(self, app):
        with app.app_context():
            inv = Invoice(org_id=1, subtotal=42000, tax_amount=9800,
                          total_amount=54000, vendor_name="TestVendor",
                          invoice_date=date.today())
            flags = _check_math_discrepancy(inv)
            assert len(flags) == 1
            assert flags[0]["type"] == "TAX_MATH_DISCREPANCY"
            assert flags[0]["severity"] == "HIGH"
            assert flags[0]["confidence"] >= 0.99

    def test_tax_math_correct_no_flag(self, app):
        with app.app_context():
            inv = Invoice(org_id=1, subtotal=84745.76, tax_amount=15254.24,
                          total_amount=100000.0, vendor_name="TestVendor",
                          invoice_date=date.today())
            flags = _check_math_discrepancy(inv)
            assert len(flags) == 0

    def test_invalid_gstin_flagged(self, app):
        with app.app_context():
            inv = Invoice(org_id=1, vendor_gstin="INVALID-GSTIN-123")
            flags = _check_gstin(inv)
            assert len(flags) == 1
            assert flags[0]["type"] == "INVALID_GSTIN_FORMAT"

    def test_valid_gstin_no_flag(self, app):
        with app.app_context():
            inv = Invoice(org_id=1, vendor_gstin="27AABCI1234D1Z5")
            flags = _check_gstin(inv)
            assert len(flags) == 0

    def test_no_gstin_no_flag(self, app):
        with app.app_context():
            inv = Invoice(org_id=1, vendor_gstin=None)
            flags = _check_gstin(inv)
            assert len(flags) == 0


class TestForecasting:
    def test_break_even_no_data(self, app):
        with app.app_context():
            from app.services.forecasting import compute_break_even
            be = compute_break_even(9999)  # Non-existent org
            assert "break_even_revenue_monthly" in be
            assert be["break_even_revenue_monthly"] >= 0

    def test_runway_no_data(self, app):
        with app.app_context():
            from app.services.forecasting import compute_runway
            runway = compute_runway(9999)
            assert "runway_days" in runway
            assert "projections" in runway
            assert len(runway["projections"]) > 0

    def test_health_score_range(self, app):
        with app.app_context():
            from app.services.forecasting import compute_health_score
            score = compute_health_score(9999)
            assert 0 <= score["score"] <= 100
            assert score["grade"] in ["A+", "A", "B", "C", "D"]

    def test_location_score_calculation(self, app):
        with app.app_context():
            from app.services.forecasting import compute_location_score
            result = compute_location_score(
                monthly_rent=50000, footfall=2000, competitors=2,
                niche_fit=8.0, parking=7.0, current_monthly_revenue=500000
            )
            assert 0 <= result["feasibility_score"] <= 100
            assert "revenue_needed_monthly" in result

    def test_dscr_no_data(self, app):
        with app.app_context():
            from app.services.forecasting import compute_dscr
            dscr = compute_dscr(9999)
            assert "dscr" in dscr
            assert "rating" in dscr
