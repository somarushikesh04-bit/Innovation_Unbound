from flask import Blueprint, jsonify, request, make_response
from app.utils.decorators import auth_required, role_required, get_current_user
from app.utils.security import (
    get_cached_health, set_cached_health, save_health_snapshot, write_audit
)
from app.models.user import UserRole
from app.services.forecasting import (
    compute_runway, compute_break_even, compute_health_score,
    compute_dscr, compute_location_score, get_ledger_aggregates
)
from app.models.invoice import CapTableEntry, LocationEvaluation
from app.models.ledger import LedgerEntry, EntryType, EntryCategory
from app.extensions import db
import random
from datetime import date, timedelta

analytics_bp = Blueprint("analytics", __name__, url_prefix="/api/analytics")



@analytics_bp.route("/dashboard", methods=["GET"])
@auth_required
def dashboard():
    user = get_current_user()
    from app.models.invoice import Invoice
    runway = compute_runway(user.org_id)
    be = compute_break_even(user.org_id)

    # Use cache if available
    health = get_cached_health(user.org_id)
    if health is None:
        health = compute_health_score(user.org_id)
        set_cached_health(user.org_id, health)
        save_health_snapshot(db, user.org_id, {**health, "monthly_burn": runway.get("monthly_burn", 0)})
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()

    flagged_count = Invoice.query.filter_by(org_id=user.org_id, status="FLAGGED").count()
    pending_count = Invoice.query.filter_by(org_id=user.org_id, status="PENDING").count()

    return jsonify({
        "health": health,
        "runway": runway,
        "break_even": be,
        "invoice_alerts": flagged_count,
        "invoice_pending": pending_count,
    })


@analytics_bp.route("/runway", methods=["GET"])
@role_required(UserRole.ACCOUNTANT, UserRole.OWNER)
def runway():
    user = get_current_user()
    return jsonify(compute_runway(user.org_id))


@analytics_bp.route("/break-even", methods=["GET"])
@role_required(UserRole.ACCOUNTANT, UserRole.OWNER)
def break_even():
    user = get_current_user()
    return jsonify(compute_break_even(user.org_id))


@analytics_bp.route("/health-score", methods=["GET"])
@auth_required
def health_score():
    user = get_current_user()
    return jsonify(compute_health_score(user.org_id))


# ── Financing & Creditworthiness ──────────────────────────────────────────────

@analytics_bp.route("/creditworthiness", methods=["GET"])
@role_required(UserRole.OWNER)
def creditworthiness():
    user = get_current_user()
    return jsonify(compute_dscr(user.org_id))


@analytics_bp.route("/investor-profile", methods=["GET"])
@role_required(UserRole.OWNER)
def investor_profile():
    user = get_current_user()
    agg = get_ledger_aggregates(user.org_id, 90)
    runway = compute_runway(user.org_id)
    health = compute_health_score(user.org_id)
    be = compute_break_even(user.org_id)
    dscr = compute_dscr(user.org_id)

    monthly_revenue = agg["revenue"] / 3.0
    monthly_cogs = agg["cogs"] / 3.0
    monthly_opex = agg["opex"] / 3.0
    gross_profit = monthly_revenue - monthly_cogs
    net_profit = gross_profit - monthly_opex
    gross_margin = (gross_profit / monthly_revenue * 100) if monthly_revenue > 0 else 0

    return jsonify({
        "generated_at": __import__("datetime").datetime.utcnow().isoformat(),
        "health_score": health["score"],
        "health_grade": health["grade"],
        "income_statement": {
            "revenue": round(monthly_revenue, 2),
            "cogs": round(monthly_cogs, 2),
            "gross_profit": round(gross_profit, 2),
            "gross_margin_pct": round(gross_margin, 1),
            "opex": round(monthly_opex, 2),
            "net_profit": round(net_profit, 2),
            "net_margin_pct": round(be["current_margin_pct"], 1),
        },
        "balance_sheet_summary": {
            "cash": round(runway["current_cash"], 2),
            "receivables": round(agg["receivables"], 2),
            "liabilities": round(agg["liabilities"], 2),
            "working_capital": round(dscr["working_capital"], 2),
        },
        "runway": {
            "days": runway["runway_days"],
            "monthly_burn": runway["monthly_burn"],
        },
        "creditworthiness": {
            "dscr": dscr["dscr"],
            "rating": dscr["rating"],
            "current_ratio": dscr["current_ratio"],
        },
    })


@analytics_bp.route("/investor-profile/export", methods=["GET"])
@role_required(UserRole.OWNER)
def export_investor_report():
    """Export a formatted investor-ready Markdown report as a downloadable file."""
    import datetime
    user = get_current_user()
    agg = get_ledger_aggregates(user.org_id, 90)
    runway = compute_runway(user.org_id)
    health = compute_health_score(user.org_id)
    be = compute_break_even(user.org_id)
    dscr = compute_dscr(user.org_id)

    monthly_revenue = agg["revenue"] / 3.0
    monthly_cogs = agg["cogs"] / 3.0
    monthly_opex = agg["opex"] / 3.0
    gross_profit = monthly_revenue - monthly_cogs
    net_profit = gross_profit - monthly_opex
    gross_margin = (gross_profit / monthly_revenue * 100) if monthly_revenue > 0 else 0
    net_margin = be.get("current_margin_pct", 0)
    now_str = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    def inr(n):
        """Format number as Indian Rupee string."""
        try:
            return f"\u20b9{n:,.0f}"
        except Exception:
            return str(n)

    lines = [
        f"# Investor Profile Report",
        f"",
        f"> **Generated:** {now_str}  ",
        f"> **Tenant ID:** {user.org_id}  ",
        f"> **Prepared by:** MSME360 Financial Intelligence Platform",
        f"",
        f"---",
        f"",
        f"## 1. Business Health Overview",
        f"",
        f"| Metric | Value |",
        f"|---|---|",
        f"| **Overall Health Score** | {health['score']:.1f} / 100 ({health['grade']}) |",
        f"| Solvency | {health['solvency']:.1f} / 100 |",
        f"| Liquidity | {health['liquidity']:.1f} / 100 |",
        f"| Profitability | {health['profitability']:.1f} / 100 |",
        f"| Operational Efficiency | {health['efficiency']:.1f} / 100 |",
        f"",
        f"---",
        f"",
        f"## 2. Income Statement (Monthly Average — Last 90 Days)",
        f"",
        f"| Item | Amount |",
        f"|---|---|",
        f"| **Revenue** | {inr(monthly_revenue)} |",
        f"| Cost of Goods Sold (COGS) | ({inr(monthly_cogs)}) |",
        f"| **Gross Profit** | {inr(gross_profit)} |",
        f"| Gross Margin | {gross_margin:.1f}% |",
        f"| Operating Expenses (OpEx) | ({inr(monthly_opex)}) |",
        f"| **Net Profit** | {inr(net_profit)} |",
        f"| Net Margin | {net_margin:.1f}% |",
        f"",
        f"---",
        f"",
        f"## 3. Balance Sheet Summary",
        f"",
        f"| Item | Amount |",
        f"|---|---|",
        f"| Cash & Equivalents | {inr(runway['current_cash'])} |",
        f"| Trade Receivables | {inr(agg['receivables'])} |",
        f"| Outstanding Liabilities | {inr(agg['liabilities'])} |",
        f"| **Net Working Capital** | {inr(dscr['working_capital'])} |",
        f"",
        f"---",
        f"",
        f"## 4. Cash Flow & Runway",
        f"",
        f"| Metric | Value |",
        f"|---|---|",
        f"| Monthly Cash Burn | {inr(runway['monthly_burn'])} |",
        f"| **Cash Runway** | **{runway['runway_days']} days** |",
        f"",
        f"---",
        f"",
        f"## 5. Creditworthiness & Debt Capacity",
        f"",
        f"| Metric | Value |",
        f"|---|---|",
        f"| **DSCR (Debt Service Coverage Ratio)** | {dscr['dscr']:.2f}x |",
        f"| Credit Rating | {dscr['rating']} |",
        f"| Current Ratio | {dscr['current_ratio']:.2f} |",
        f"| Estimated Loan Eligibility | {inr(dscr.get('loan_eligibility', 0))} |",
        f"",
        f"---",
        f"",
        f"## 6. Break-Even Analysis",
        f"",
        f"| Metric | Value |",
        f"|---|---|",
        f"| Break-Even Revenue (Monthly) | {inr(be.get('break_even_revenue_monthly', 0))} |",
        f"| Contribution Margin Ratio | {be.get('contribution_margin_ratio', 0):.1%} |",
        f"",
        f"---",
        f"",
        f"*This report was auto-generated by MSME360. All figures are based on ledger data",
        f"recorded in the platform and are for internal decision-making purposes only.*",
    ]

    report_md = "\n".join(lines)
    filename = f"investor_report_{datetime.datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.md"

    resp = make_response(report_md)
    resp.headers["Content-Type"] = "text/markdown; charset=utf-8"
    resp.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    return resp


# ── Cap Table ─────────────────────────────────────────────────────────────────

@analytics_bp.route("/cap-table", methods=["GET"])
@role_required(UserRole.OWNER)
def get_cap_table():
    user = get_current_user()
    entries = CapTableEntry.query.filter_by(org_id=user.org_id).all()
    total_equity = sum(e.equity_percentage for e in entries)
    total_invested = sum(e.invested_amount for e in entries)

    return jsonify({
        "entries": [e.to_dict() for e in entries],
        "total_equity_allocated": round(total_equity, 2),
        "total_invested": round(total_invested, 2),
        "unallocated": round(max(0, 100 - total_equity), 2),
    })


@analytics_bp.route("/cap-table", methods=["POST"])
@role_required(UserRole.OWNER)
def add_cap_table_entry():
    user = get_current_user()
    data = request.get_json(silent=True) or {}
    required = ["stakeholder_name", "stakeholder_type", "equity_percentage"]
    for f in required:
        if not data.get(f):
            return jsonify({"error": f"Field '{f}' is required"}), 400

    entry = CapTableEntry(
        org_id=user.org_id,
        stakeholder_name=str(data["stakeholder_name"])[:200],
        stakeholder_type=str(data["stakeholder_type"]).upper()[:20],
        equity_percentage=float(data["equity_percentage"]),
        shares_count=int(data.get("shares_count", 0)),
        invested_amount=float(data.get("invested_amount", 0)),
        round_name=str(data.get("round_name", "Seed"))[:100],
    )
    db.session.add(entry)
    db.session.commit()
    return jsonify({"message": "Stakeholder added", "entry": entry.to_dict()}), 201


@analytics_bp.route("/dilution-simulator", methods=["POST"])
@role_required(UserRole.OWNER)
def dilution_simulator():
    user = get_current_user()
    data = request.get_json(silent=True) or {}

    new_investment = float(data.get("new_investment", 0))
    pre_money_valuation = float(data.get("pre_money_valuation", 1))
    post_money = pre_money_valuation + new_investment
    new_investor_pct = (new_investment / post_money) * 100

    entries = CapTableEntry.query.filter_by(org_id=user.org_id).all()
    dilution_factor = 1 - (new_investor_pct / 100)

    table = []
    for e in entries:
        diluted = e.equity_percentage * dilution_factor
        table.append({
            "stakeholder": e.stakeholder_name,
            "type": e.stakeholder_type,
            "before": e.equity_percentage,
            "after": round(diluted, 2),
            "dilution": round(e.equity_percentage - diluted, 2),
        })

    table.append({
        "stakeholder": "New Investor",
        "type": "INVESTOR",
        "before": 0.0,
        "after": round(new_investor_pct, 2),
        "dilution": 0.0,
    })

    return jsonify({
        "pre_money_valuation": pre_money_valuation,
        "new_investment": new_investment,
        "post_money_valuation": post_money,
        "new_investor_equity_pct": round(new_investor_pct, 2),
        "cap_table_after": table,
    })


# ── Location Intelligence ─────────────────────────────────────────────────────

@analytics_bp.route("/location/evaluate", methods=["POST"])
@role_required(UserRole.ACCOUNTANT, UserRole.OWNER)
def evaluate_location():
    user = get_current_user()
    data = request.get_json(silent=True) or {}

    required = ["location_name", "monthly_rent", "footfall_estimate"]
    for f in required:
        if data.get(f) is None:
            return jsonify({"error": f"Field '{f}' is required"}), 400

    agg = get_ledger_aggregates(user.org_id, 90)
    current_revenue = agg["revenue"] / 3.0

    score_data = compute_location_score(
        monthly_rent=float(data["monthly_rent"]),
        footfall=int(data["footfall_estimate"]),
        competitors=int(data.get("competitor_count", 0)),
        niche_fit=float(data.get("niche_fit_score", 5)),
        parking=float(data.get("parking_access_score", 5)),
        current_monthly_revenue=current_revenue,
    )

    loc = LocationEvaluation(
        org_id=user.org_id,
        location_name=str(data["location_name"])[:200],
        monthly_rent=float(data["monthly_rent"]),
        footfall_estimate=int(data["footfall_estimate"]),
        competitor_count=int(data.get("competitor_count", 0)),
        niche_fit_score=float(data.get("niche_fit_score", 5)),
        parking_access_score=float(data.get("parking_access_score", 5)),
        feasibility_score=score_data["feasibility_score"],
        notes=str(data.get("notes", ""))[:1000],
    )
    db.session.add(loc)
    db.session.commit()

    return jsonify({
        "evaluation": loc.to_dict(),
        "score_breakdown": score_data,
    }), 201


@analytics_bp.route("/location/history", methods=["GET"])
@role_required(UserRole.ACCOUNTANT, UserRole.OWNER)
def location_history():
    user = get_current_user()
    locs = LocationEvaluation.query.filter_by(org_id=user.org_id).order_by(
        LocationEvaluation.feasibility_score.desc()
    ).all()
    return jsonify({"evaluations": [l.to_dict() for l in locs]})


@analytics_bp.route("/location/<int:loc_id>", methods=["DELETE"])
@role_required(UserRole.ACCOUNTANT, UserRole.OWNER)
def delete_location(loc_id):
    user = get_current_user()
    loc = LocationEvaluation.query.filter_by(id=loc_id, org_id=user.org_id).first_or_404()
    db.session.delete(loc)
    db.session.commit()
    return jsonify({"message": "Location evaluation deleted"})


@analytics_bp.route("/cap-table/<int:entry_id>", methods=["DELETE"])
@role_required(UserRole.ACCOUNTANT, UserRole.OWNER)
def delete_cap_table_entry(entry_id):
    user = get_current_user()
    entry = CapTableEntry.query.filter_by(id=entry_id, org_id=user.org_id).first_or_404()
    db.session.delete(entry)
    db.session.commit()
    return jsonify({"message": "Cap table entry deleted"})


# ── Demo Data Seeder ──────────────────────────────────────────────────────────

@analytics_bp.route("/seed-demo", methods=["POST"])
@role_required(UserRole.ACCOUNTANT, UserRole.OWNER)
def seed_demo_data():
    """Seed 90 days of realistic Indian MSME financial data for demo/testing."""
    user = get_current_user()
    org_id = user.org_id

    # Prevent double-seeding
    existing = LedgerEntry.query.filter_by(org_id=org_id).count()
    if existing >= 30:
        return jsonify({"message": f"Demo data already present ({existing} entries). Clear existing data first if you want to re-seed.", "seeded": 0}), 200

    rng = random.Random(org_id * 42)  # deterministic per org

    # Realistic Indian MSME profile: retail/manufacturing, ₹4-5L/month revenue
    entries_to_create = []
    today = date.today()

    # Revenue patterns — 3 months of sales data
    for month_offset in range(3):
        month_start = today - timedelta(days=90 - month_offset * 30)

        # 8-12 sales transactions per month
        for week in range(4):
            txn_date = month_start + timedelta(days=week * 7 + rng.randint(0, 4))
            if txn_date > today:
                txn_date = today - timedelta(days=rng.randint(1, 5))

            # Cash sales
            entries_to_create.append(LedgerEntry(
                org_id=org_id, entry_type=EntryType.CREDIT.value,
                category=EntryCategory.SALES_CASH.value,
                amount=round(rng.uniform(45000, 85000), 2),
                description=rng.choice(["Retail sales - walk-in customers", "Wholesale order - cash payment",
                                        "Product sales batch", "Counter sales revenue", "Direct sales"]),
                party_name=rng.choice(["Retail Customers", "Walk-in Sales", "Direct Buyers"]),
                reference_date=txn_date, created_by=user.id,
            ))

        # 2-3 credit sales per month
        for _ in range(rng.randint(2, 3)):
            txn_date = month_start + timedelta(days=rng.randint(0, 28))
            if txn_date > today:
                txn_date = today - timedelta(days=rng.randint(1, 5))
            entries_to_create.append(LedgerEntry(
                org_id=org_id, entry_type=EntryType.CREDIT.value,
                category=EntryCategory.SALES_CREDIT.value,
                amount=round(rng.uniform(80000, 180000), 2),
                description=rng.choice(["B2B order - 30 day credit terms", "Institutional supply - invoice raised",
                                        "Bulk order - credit sale"]),
                party_name=rng.choice(["Metro Distributors", "City Wholesalers", "Apex Trading Co",
                                        "National Retail Chain", "Government Supply"]),
                reference_date=txn_date, created_by=user.id,
            ))

        # COGS — raw materials, inventory purchases
        for _ in range(rng.randint(3, 5)):
            txn_date = month_start + timedelta(days=rng.randint(0, 28))
            if txn_date > today:
                txn_date = today - timedelta(days=rng.randint(1, 5))
            entries_to_create.append(LedgerEntry(
                org_id=org_id, entry_type=EntryType.DEBIT.value,
                category=EntryCategory.COGS.value,
                amount=round(rng.uniform(25000, 60000), 2),
                description=rng.choice(["Raw material purchase", "Inventory restocking", "Goods procurement",
                                        "Production input materials", "Stock replenishment"]),
                party_name=rng.choice(["Steel India Ltd", "Gupta Traders", "Maharashtra Supplies",
                                        "National Raw Materials", "Bharat Commodities"]),
                reference_date=txn_date, created_by=user.id,
            ))

        # OPEX — recurring monthly expenses
        opex_items = [
            (15000, 25000, "Staff salaries & wages", "Payroll"),
            (8000, 15000, "Shop/warehouse rent", "Landlord"),
            (2000, 5000, "Electricity & utilities", "MSEB / BESCOM"),
            (1500, 4000, "Internet, phone & communications", "Telecom Provider"),
            (3000, 8000, "Transportation & logistics", "Courier/Transport"),
            (1000, 3000, "Office supplies & stationery", "Stationery Mart"),
        ]
        for min_amt, max_amt, desc, party in opex_items:
            txn_date = month_start + timedelta(days=rng.randint(1, 5))
            if txn_date > today:
                txn_date = today - timedelta(days=rng.randint(1, 5))
            entries_to_create.append(LedgerEntry(
                org_id=org_id, entry_type=EntryType.DEBIT.value,
                category=EntryCategory.OPEX.value,
                amount=round(rng.uniform(min_amt, max_amt), 2),
                description=desc, party_name=party,
                reference_date=txn_date, created_by=user.id,
            ))

    # Outstanding receivables
    for _ in range(3):
        txn_date = today - timedelta(days=rng.randint(5, 25))
        entries_to_create.append(LedgerEntry(
            org_id=org_id, entry_type=EntryType.CREDIT.value,
            category=EntryCategory.RECEIVABLE.value,
            amount=round(rng.uniform(40000, 120000), 2),
            description="Receivable — payment pending from customer",
            party_name=rng.choice(["Sunrise Retailers", "Peak Distributors", "City Mart Chain"]),
            reference_date=txn_date, created_by=user.id,
        ))

    # Liability entries
    for _ in range(2):
        txn_date = today - timedelta(days=rng.randint(10, 60))
        entries_to_create.append(LedgerEntry(
            org_id=org_id, entry_type=EntryType.DEBIT.value,
            category=EntryCategory.LIABILITY.value,
            amount=round(rng.uniform(15000, 35000), 2),
            description=rng.choice(["Working capital loan EMI", "Business loan repayment", "Term loan installment"]),
            party_name=rng.choice(["SBI Business Loan", "HDFC MSME Loan", "SIDBI Working Capital"]),
            reference_date=txn_date, created_by=user.id,
        ))

    db.session.bulk_save_objects(entries_to_create)
    db.session.commit()

    return jsonify({
        "message": f"✅ Demo data seeded successfully! {len(entries_to_create)} realistic transactions added covering 90 days of Indian MSME operations.",
        "seeded": len(entries_to_create),
        "period": "Last 90 days",
        "profile": "Retail/Manufacturing MSME, ₹4-5L/month revenue range",
    }), 201

