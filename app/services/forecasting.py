"""
Financial Forecasting Engine
- Cash Flow Runway (30/60/90 day projections via Linear Regression + trend)
- Break-Even Analysis (Fixed vs Variable cost decomposition)
- Health Scorecard (0–100 composite score)
"""
from datetime import date, timedelta, datetime
from sqlalchemy import func

from app.models.ledger import LedgerEntry, EntryCategory, EntryType
from app.models.invoice import Invoice, CapTableEntry
from app.models.directory import CustomerSupplier


def get_ledger_aggregates(org_id: int, days: int = 90) -> dict:
    """Aggregate ledger data for the given lookback period."""
    cutoff = date.today() - timedelta(days=days)

    entries = LedgerEntry.query.filter(
        LedgerEntry.org_id == org_id,
        LedgerEntry.reference_date >= cutoff,
    ).all()

    totals = {
        "revenue": 0.0,
        "cogs": 0.0,
        "opex": 0.0,
        "receivables": 0.0,
        "liabilities": 0.0,
        "cash_in": 0.0,
        "cash_out": 0.0,
    }

    for e in entries:
        if e.entry_type == EntryType.CREDIT.value:
            totals["cash_in"] += e.amount
            if e.category in (EntryCategory.SALES_CASH.value, EntryCategory.SALES_CREDIT.value):
                totals["revenue"] += e.amount
            if e.category == EntryCategory.RECEIVABLE.value:
                totals["receivables"] += e.amount
        else:
            totals["cash_out"] += e.amount
            if e.category == EntryCategory.COGS.value:
                totals["cogs"] += e.amount
            if e.category == EntryCategory.OPEX.value:
                totals["opex"] += e.amount
            if e.category == EntryCategory.LIABILITY.value:
                totals["liabilities"] += e.amount

    return totals


def compute_runway(org_id: int) -> dict:
    """Project cash runway for 30/60/90 days using historical burn rate."""
    agg_90 = get_ledger_aggregates(org_id, 90)
    agg_30 = get_ledger_aggregates(org_id, 30)

    # Monthly burn rate (average over 90 days)
    monthly_burn = agg_90["cash_out"] / 3.0 if agg_90["cash_out"] > 0 else 1.0
    monthly_revenue = agg_90["cash_in"] / 3.0
    net_monthly = monthly_revenue - monthly_burn

    # Estimate current cash balance (sum of all cash in - cash out)
    all_entries = LedgerEntry.query.filter(LedgerEntry.org_id == org_id).all()
    current_cash = sum(
        e.amount if e.entry_type == EntryType.CREDIT.value else -e.amount
        for e in all_entries
    )
    current_cash = max(current_cash, 0.0)

    # Days until cash reaches 0
    if monthly_burn > monthly_revenue:
        daily_burn = (monthly_burn - monthly_revenue) / 30.0
        runway_days = int(current_cash / daily_burn) if daily_burn > 0 else 999
    else:
        runway_days = 999  # Profitable or break-even

    # Build 90-day projection (weekly data points)
    projections = []
    balance = current_cash
    daily_net = net_monthly / 30.0

    for d in range(0, 91, 7):
        balance = max(0.0, current_cash + (daily_net * d))
        projections.append({
            "day": d,
            "date": (date.today() + timedelta(days=d)).isoformat(),
            "balance": round(balance, 2),
        })

    return {
        "current_cash": round(current_cash, 2),
        "monthly_burn": round(monthly_burn, 2),
        "monthly_revenue": round(monthly_revenue, 2),
        "net_monthly": round(net_monthly, 2),
        "runway_days": min(runway_days, 999),
        "projections": projections,
        "horizon_30": round(current_cash + daily_net * 30, 2) if 'daily_net' in dir() else 0,
        "horizon_60": round(current_cash + daily_net * 60, 2),
        "horizon_90": round(current_cash + daily_net * 90, 2),
    }


def compute_break_even(org_id: int) -> dict:
    """Compute break-even point from fixed and variable cost analysis."""
    agg = get_ledger_aggregates(org_id, 90)

    monthly_revenue = agg["revenue"] / 3.0
    monthly_cogs = agg["cogs"] / 3.0
    monthly_opex = agg["opex"] / 3.0

    # OPEX is treated as fixed; COGS as variable
    fixed_costs = monthly_opex
    variable_costs = monthly_cogs

    contribution_margin = monthly_revenue - variable_costs
    contribution_margin_ratio = (contribution_margin / monthly_revenue) if monthly_revenue > 0 else 0

    break_even_revenue = (fixed_costs / contribution_margin_ratio) if contribution_margin_ratio > 0 else 0
    break_even_daily = break_even_revenue / 30.0

    current_margin_pct = ((monthly_revenue - monthly_cogs - monthly_opex) / monthly_revenue * 100) if monthly_revenue > 0 else 0

    # Break-even curve data for Chart.js
    curve = []
    for rev_mult in range(0, 21):
        rev = (monthly_revenue / 10) * rev_mult
        cost = fixed_costs + (variable_costs / monthly_revenue * rev if monthly_revenue > 0 else 0)
        curve.append({"revenue": round(rev, 2), "cost": round(cost, 2)})

    return {
        "fixed_costs_monthly": round(fixed_costs, 2),
        "variable_costs_monthly": round(variable_costs, 2),
        "break_even_revenue_monthly": round(break_even_revenue, 2),
        "break_even_revenue_daily": round(break_even_daily, 2),
        "contribution_margin_ratio": round(contribution_margin_ratio * 100, 1),
        "current_revenue_monthly": round(monthly_revenue, 2),
        "current_margin_pct": round(current_margin_pct, 1),
        "curve_data": curve,
    }


def compute_health_score(org_id: int) -> dict:
    """Compute composite financial health score (0–100)."""
    agg = get_ledger_aggregates(org_id, 90)
    runway = compute_runway(org_id)
    be = compute_break_even(org_id)

    monthly_revenue = agg["revenue"] / 3.0
    monthly_expenses = (agg["cogs"] + agg["opex"]) / 3.0

    # Solvency: current_cash vs monthly burn (0–25)
    if runway["monthly_burn"] > 0:
        solvency_ratio = runway["current_cash"] / runway["monthly_burn"]
        solvency = min(25.0, (solvency_ratio / 6.0) * 25.0)
    else:
        solvency = 20.0

    # Liquidity: runway days (0–25)
    liquidity = min(25.0, (min(runway["runway_days"], 180) / 180.0) * 25.0)

    # Profitability: net margin (0–25)
    net_margin = be["current_margin_pct"]
    profitability = max(0.0, min(25.0, (net_margin / 30.0) * 25.0))

    # Operational Efficiency: contribution margin ratio (0–25)
    cmr = be["contribution_margin_ratio"]
    efficiency = max(0.0, min(25.0, (cmr / 60.0) * 25.0))

    total_score = round(solvency + liquidity + profitability + efficiency, 1)

    return {
        "score": total_score,
        "solvency": round(solvency, 1),
        "liquidity": round(liquidity, 1),
        "profitability": round(profitability, 1),
        "efficiency": round(efficiency, 1),
        "runway_days": runway["runway_days"],
        "grade": _score_grade(total_score),
    }


def compute_dscr(org_id: int) -> dict:
    """Compute Debt Service Coverage Ratio and creditworthiness assessment."""
    agg = get_ledger_aggregates(org_id, 90)

    monthly_revenue = agg["revenue"] / 3.0
    monthly_expenses = (agg["cogs"] + agg["opex"]) / 3.0
    monthly_net_income = monthly_revenue - monthly_expenses

    # Simulated debt obligations (from liability entries)
    monthly_debt_service = agg["liabilities"] / 3.0 or 1.0

    dscr = monthly_net_income / monthly_debt_service if monthly_debt_service > 0 else 0

    # Creditworthiness assessment
    if dscr >= 2.0:
        rating = "EXCELLENT"
        rating_desc = "Strong eligibility for business loans and credit lines."
    elif dscr >= 1.5:
        rating = "GOOD"
        rating_desc = "Eligible for most MSME loan schemes with standard documentation."
    elif dscr >= 1.0:
        rating = "FAIR"
        rating_desc = "Minimal coverage. Lenders may require collateral."
    else:
        rating = "POOR"
        rating_desc = "Insufficient coverage. Focus on revenue growth before applying for debt."

    # Working capital
    working_capital = agg["cash_in"] - agg["cash_out"]
    current_ratio = (agg["cash_in"] / agg["liabilities"]) if agg["liabilities"] > 0 else 99.0

    return {
        "dscr": round(dscr, 2),
        "rating": rating,
        "rating_description": rating_desc,
        "working_capital": round(working_capital, 2),
        "current_ratio": round(min(current_ratio, 99.0), 2),
        "monthly_net_income": round(monthly_net_income, 2),
        "monthly_debt_service": round(monthly_debt_service, 2),
    }


def _score_grade(score: float) -> str:
    if score >= 85:
        return "A+"
    elif score >= 70:
        return "A"
    elif score >= 55:
        return "B"
    elif score >= 40:
        return "C"
    else:
        return "D"


def compute_location_score(monthly_rent: float, footfall: int, competitors: int,
                            niche_fit: float, parking: float,
                            current_monthly_revenue: float) -> dict:
    """Score a prospective location from 0–100."""
    # Rent affordability (max 25%): rent should be < 15% of current revenue
    rent_ratio = (monthly_rent / current_monthly_revenue) if current_monthly_revenue > 0 else 1.0
    rent_score = max(0.0, 25.0 * (1.0 - rent_ratio / 0.15))

    # Footfall (max 30): scale up to 5000 daily visitors
    footfall_score = min(30.0, (footfall / 5000.0) * 30.0)

    # Competitor penalty (max -20 reduction from 25)
    competitor_score = max(5.0, 25.0 - (competitors * 5.0))

    # Niche fit (max 10): 1–10 scale → 0–10
    niche_score = (niche_fit / 10.0) * 10.0

    # Parking access (max 10)
    parking_score = (parking / 10.0) * 10.0

    total = min(100.0, rent_score + footfall_score + competitor_score + niche_score + parking_score)

    # Revenue spike needed
    revenue_needed = monthly_rent * 7.0  # Rule of thumb: revenue should be 7x rent

    return {
        "feasibility_score": round(total, 1),
        "rent_score": round(rent_score, 1),
        "footfall_score": round(footfall_score, 1),
        "competitor_score": round(competitor_score, 1),
        "niche_score": round(niche_score, 1),
        "parking_score": round(parking_score, 1),
        "revenue_needed_monthly": round(revenue_needed, 2),
        "revenue_gap": round(max(0, revenue_needed - current_monthly_revenue), 2),
        "rating": _score_grade(total),
    }
