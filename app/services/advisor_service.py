"""
AI Business Advisor Service
Sends grounded, tenant-scoped financial context to Gemini API for actionable advice.
Falls back to rule-based answers when API is unavailable.
"""
import json
import os
import requests
from datetime import date

from app.services.forecasting import (
    get_ledger_aggregates, compute_runway, compute_break_even, compute_health_score
)


QUICK_INSIGHTS = [
    "Can I hire two more staff next month?",
    "Which suppliers represent the highest margin drag?",
    "What is my true runway if receivables delay 15 days?",
    "Should I expand to a second location now?",
    "Am I eligible for an MSME loan?",
    "What expenses can I cut to improve cash flow?",
]

GEMINI_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"


def build_financial_context(org_id: int) -> str:
    """Build a structured financial summary for the LLM prompt."""
    try:
        agg = get_ledger_aggregates(org_id, 90)
        runway = compute_runway(org_id)
        be = compute_break_even(org_id)
        health = compute_health_score(org_id)

        monthly_revenue = agg["revenue"] / 3.0
        monthly_expenses = (agg["cogs"] + agg["opex"]) / 3.0

        ctx = f"""
MSME Financial Summary (Last 90 Days):
- Monthly Revenue: ₹{monthly_revenue:,.0f}
- Monthly COGS: ₹{agg['cogs']/3:,.0f}
- Monthly Operating Expenses: ₹{agg['opex']/3:,.0f}
- Net Monthly Cash Flow: ₹{(monthly_revenue - monthly_expenses):,.0f}
- Current Cash Balance: ₹{runway['current_cash']:,.0f}
- Monthly Burn Rate: ₹{runway['monthly_burn']:,.0f}
- Cash Runway: {runway['runway_days']} days
- Break-Even Revenue/Month: ₹{be['break_even_revenue_monthly']:,.0f}
- Current Profit Margin: {be['current_margin_pct']:.1f}%
- Contribution Margin Ratio: {be['contribution_margin_ratio']:.1f}%
- Health Score: {health['score']}/100 (Grade: {health['grade']})
- Outstanding Receivables: ₹{agg['receivables']:,.0f}
- Outstanding Liabilities: ₹{agg['liabilities']:,.0f}
"""
        return ctx.strip()
    except Exception as e:
        return "Financial data not available for this period."


def ask_advisor(question: str, org_id: int) -> dict:
    """Get AI-powered advice grounded in tenant financial data."""
    api_key = os.getenv("GEMINI_API_KEY", "")
    ctx = build_financial_context(org_id)

    system_prompt = f"""You are MSME360's AI Business Advisor — a trusted financial expert for micro, small, and medium enterprises in India.
You have access to the business's real financial data shown below. Always ground your answers in this data.
Be specific, actionable, and practical. Keep responses concise (3–5 sentences) with clear recommendations.
Use Indian currency context (₹, crore, lakh) where relevant.

{ctx}"""

    if api_key and len(api_key) > 20:
        try:
            payload = {
                "contents": [
                    {"role": "user", "parts": [{"text": f"{system_prompt}\n\nUser Question: {question}"}]}
                ],
                "generationConfig": {
                    "temperature": 0.7,
                    "maxOutputTokens": 512,
                }
            }
            resp = requests.post(
                f"{GEMINI_ENDPOINT}?key={api_key}",
                json=payload,
                timeout=15,
            )
            if resp.status_code == 200:
                data = resp.json()
                answer = data["candidates"][0]["content"]["parts"][0]["text"]
                return {"answer": answer, "source": "gemini", "context_used": True}
            # Log non-200 but don't surface to user — fall through to rules
        except Exception:
            pass

    # Rule-based fallback — always returns a useful answer
    answer = _rule_based_response(question, org_id, ctx)
    return {"answer": answer, "source": "rule_based", "context_used": True}


def _rule_based_response(question: str, org_id: int, ctx: str) -> str:
    """Heuristic advisor responses — works with or without ledger data."""
    q = question.lower()

    # Try to get real financial data first
    has_data = False
    runway = be = agg = None
    monthly_revenue = monthly_opex = 0.0
    try:
        runway = compute_runway(org_id)
        be = compute_break_even(org_id)
        agg = get_ledger_aggregates(org_id, 90)
        monthly_revenue = agg["revenue"] / 3.0
        monthly_opex = agg["opex"] / 3.0
        has_data = monthly_revenue > 0 or agg["cash_out"] > 0
    except Exception:
        pass

    # ── With real data ────────────────────────────────────────────────────────
    if has_data:
        if "hire" in q or "staff" in q or "employee" in q:
            avg_salary = 25000  # Assumed average monthly salary
            impact = avg_salary * 2
            new_runway = (runway["current_cash"]) / (runway["monthly_burn"] + impact / 30) if runway["monthly_burn"] + impact / 30 > 0 else 999
            if new_runway > 90:
                return (f"Based on your current cash balance of ₹{runway['current_cash']:,.0f} and burn rate of ₹{runway['monthly_burn']:,.0f}/month, "
                        f"hiring 2 staff (est. ₹{impact:,}/month additional cost) would reduce your runway to ~{int(new_runway)} days. "
                        f"This appears manageable. Ensure you have receivables cleared first.")
            else:
                return (f"Caution: Hiring 2 staff would add ~₹{impact:,}/month to your burn rate. "
                        f"Your runway would shrink to ~{int(new_runway)} days — below the 90-day safety buffer. "
                        f"Consider hiring 1 staff member or waiting until revenue increases by ₹{impact*3:,}/month.")

        elif "runway" in q and "receiv" in q:
            delayed = agg["receivables"]
            current_cash_adj = runway["current_cash"] - delayed
            if runway["monthly_burn"] > 0:
                adj_runway = int(max(0, current_cash_adj) / (runway["monthly_burn"] / 30))
            else:
                adj_runway = 999
            return (f"If your ₹{delayed:,.0f} in outstanding receivables are delayed by 15 days, "
                    f"your effective cash balance drops to ₹{max(0, current_cash_adj):,.0f}. "
                    f"This would cut your runway from {runway['runway_days']} to approximately {adj_runway} days. "
                    f"Prioritize collections from your top debtors immediately.")

        elif "supplier" in q or "vendor" in q or "margin" in q:
            cogs_pct = agg['cogs']/3/monthly_revenue*100 if monthly_revenue > 0 else 0
            return (f"Your COGS represents {cogs_pct:.1f}% of revenue over 90 days. "
                    f"Review vendors with invoices above your 90-day average and renegotiate credit terms. "
                    f"Targeting a 5% reduction in COGS would add ~₹{monthly_revenue*0.05:,.0f} to monthly profit.")

        elif "loan" in q or "credit" in q or "borrow" in q or "msme" in q:
            from app.services.forecasting import compute_dscr
            dscr = compute_dscr(org_id)
            return (f"Your current DSCR is {dscr['dscr']:.2f} ({dscr['rating']}). {dscr['rating_description']} "
                    f"Working capital is ₹{dscr['working_capital']:,.0f}. "
                    f"Maintain a minimum 3-month expense reserve before taking on new debt.")

        elif "expand" in q or "location" in q or "branch" in q or "second" in q:
            if runway["runway_days"] > 120 and be["current_margin_pct"] > 15:
                return (f"Your financial position (Runway: {runway['runway_days']} days, Margin: {be['current_margin_pct']:.1f}%) "
                        f"supports cautious expansion. Use the Location Intelligence tool to evaluate sites — "
                        f"target locations where monthly rent is below ₹{monthly_revenue * 0.12:,.0f} (12% of revenue).")
            else:
                return (f"With a {runway['runway_days']}-day runway and {be['current_margin_pct']:.1f}% margin, "
                        f"expansion carries significant risk right now. "
                        f"Grow current location revenue by 25% first before committing to a new lease.")

        elif "cut" in q or "reduce" in q or "expense" in q or "cost" in q:
            return (f"Your monthly operating expenses are ₹{monthly_opex:,.0f}. "
                    f"Key areas to review: discretionary OPEX (travel, subscriptions), supplier payment terms, and inventory carrying costs. "
                    f"A 10% reduction in OPEX would extend your runway by ~{int(runway['current_cash'] * 0.1 / max(runway['monthly_burn']/30, 1))} days.")

        elif "runway" in q or "cash" in q or "burn" in q or "survive" in q:
            return (f"Your cash runway is {runway['runway_days']} days at the current burn rate of ₹{runway['monthly_burn']:,.0f}/month. "
                    f"Current cash balance: ₹{runway['current_cash']:,.0f}. "
                    f"{'You are currently profitable — maintain this trajectory.' if runway['net_monthly'] >= 0 else 'You are burning cash net-negative. Accelerate collections and review discretionary spend immediately.'}")

        elif "profit" in q or "revenue" in q or "income" in q or "sales" in q:
            return (f"Monthly revenue: ₹{monthly_revenue:,.0f} | Net margin: {be['current_margin_pct']:.1f}% | Break-even: ₹{be['break_even_revenue_monthly']:,.0f}/month. "
                    f"{'You are above break-even — focus on scaling.' if monthly_revenue > be['break_even_revenue_monthly'] else 'You are below break-even. Reducing fixed costs or growing revenue is the priority.'}")

        elif "gst" in q or "tax" in q or "compliance" in q:
            return (f"Based on your ₹{monthly_revenue:,.0f}/month revenue, ensure you are GST-registered if annual turnover exceeds ₹40 lakh (₹20 lakh for services). "
                    f"File GSTR-1 by the 11th and GSTR-3B by the 20th of each month. "
                    f"Set aside {18 if monthly_revenue > 0 else 18}% of revenue in a separate account for GST remittance.")

        else:
            health_score = compute_health_score(org_id)
            return (f"Based on your financials: Revenue ₹{monthly_revenue:,.0f}/month, Runway {runway['runway_days']} days, "
                    f"Health Score {health_score['score']}/100 (Grade {health_score['grade']}). "
                    f"Focus on clearing ₹{agg['receivables']:,.0f} in receivables and maintaining your current burn rate discipline. "
                    f"Ask me a specific question about hiring, loans, expansion, or cost reduction.")

    # ── Zero-data fallback — smart generic MSME advice ────────────────────────
    if "hire" in q or "staff" in q or "employee" in q:
        return ("Before hiring, ensure you have at least 6 months of that employee's salary in reserve. "
                "For Indian MSMEs, a good rule of thumb: only hire when your revenue consistently exceeds your break-even point for 3 consecutive months. "
                "Start by adding your ledger transactions so I can give you a precise hiring recommendation based on your actual runway. "
                "Also consider PF (12% employer contribution) and ESIC costs when budgeting.")

    elif "loan" in q or "credit" in q or "borrow" in q or "msme" in q:
        return ("For MSME loans in India, banks evaluate your DSCR (Debt Service Coverage Ratio) — ideally above 1.5. "
                "Key government schemes: MUDRA (up to ₹10L), CGTMSE (collateral-free up to ₹2Cr), and PM SVANidhi for micro-enterprises. "
                "Maintain a current ratio above 1.3 and 12 months of ITR filings to maximize eligibility. "
                "Add your financial transactions and I'll calculate your exact loan eligibility.")

    elif "expand" in q or "location" in q or "branch" in q or "second" in q:
        return ("For expansion, a classic rule: monthly rent should not exceed 10–12% of expected monthly revenue from that location. "
                "Before committing, evaluate: footfall, competitor density, and whether your current unit is consistently profitable for 6+ months. "
                "Use the Location Intelligence tool (left sidebar) to score specific sites. "
                "Add your ledger data and I'll calculate whether your financial position supports expansion.")

    elif "runway" in q or "cash" in q or "burn" in q or "survive" in q:
        return ("Cash runway is the #1 survival metric for MSMEs. "
                "Ideal: maintain 90+ days of expenses in cash reserves at all times. "
                "To calculate yours: add your last 3 months of income and expense entries in the Ledger, and I'll compute your exact runway, burn rate, and 90-day projection. "
                "Quick tips: invoice customers within 24h of delivery, offer 2% early-payment discounts, and negotiate 30–45 day payment terms with suppliers.")

    elif "supplier" in q or "vendor" in q or "margin" in q or "cost" in q or "expense" in q:
        return ("For Indian MSMEs, COGS typically ranges from 50–70% of revenue depending on the sector (manufacturing: 60–70%, retail: 55–65%, services: 20–35%). "
                "If your gross margin is below 30%, you need to either raise prices or renegotiate supplier terms. "
                "Common quick wins: consolidate purchases with fewer suppliers for volume discounts, switch to credit purchases where possible, and review inventory turnover. "
                "Log your transactions and I'll identify your specific cost reduction opportunities.")

    elif "profit" in q or "revenue" in q or "income" in q or "sales" in q:
        return ("Profitability for MSMEs depends heavily on pricing strategy and cost control. "
                "Track: gross margin (revenue minus COGS) and net margin (after all expenses). "
                "A healthy MSME should target 15–25% net margin. "
                "Add your sales and expense data to the Ledger and I'll calculate your break-even point, contribution margin, and give you specific growth targets.")

    elif "gst" in q or "tax" in q or "compliance" in q:
        return ("GST compliance essentials for Indian MSMEs: "
                "Register if turnover exceeds ₹40 lakh/year (₹20L for services). "
                "File GSTR-1 (outward supplies) by the 11th and GSTR-3B (summary return) by the 20th of each month. "
                "Maintain a dedicated GST liability account — set aside 18% of each B2C sale and 18% collected on B2B invoices. "
                "Input Tax Credit (ITC) can significantly reduce your GST outgo — ensure all purchase invoices from GST-registered vendors are uploaded in the Invoices section.")

    elif "invest" in q or "fund" in q or "equity" in q or "investor" in q:
        return ("Before approaching investors, prepare: 3 years of financials (or projections for startups), a clear unit economics story, and your growth trajectory. "
                "For MSME financing, consider: angel investors (₹25L–2Cr), SIDBI venture funds, or government-backed schemes like Startup India. "
                "Key metrics investors look for: revenue growth rate, gross margin, customer retention, and founder commitment. "
                "Use the Financing & Cap Table section to model your equity structure and dilution impact.")

    elif "health" in q or "score" in q or "grade" in q:
        return ("The MSME360 Health Score (0–100) measures 4 dimensions: "
                "Solvency (cash vs burn rate), Liquidity (runway days), Profitability (net margin), and Efficiency (contribution margin ratio). "
                "Score ≥85: A+ (Excellent) | 70–84: A (Good) | 55–69: B (Average) | 40–54: C (Needs attention) | <40: D (Critical). "
                "Start by adding your last 3 months of transactions to get your personalized score.")

    else:
        return ("I'm MSME360's AI Business Advisor — here to help you make smarter financial decisions. "
                "I can answer questions about: cash flow & runway, hiring decisions, loan eligibility, expansion planning, cost reduction, GST compliance, and break-even analysis. "
                "For personalized advice grounded in your actual numbers, add your income and expense entries in the Ledger section, then ask me again. "
                "Try asking: 'What is my cash runway?', 'Can I hire 2 staff?', 'Am I eligible for an MSME loan?', or 'How do I reduce my expenses?'")
