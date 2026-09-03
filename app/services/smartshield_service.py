"""
app/services/smartshield_service.py
SmartShield — AI-Powered Banking Fraud Detection Engine

Real-life calibration sources:
  - RBI Annual Report 2023: avg UPI fraud txn = ₹48,200 vs avg legit = ₹3,200
  - NPCI Cybercrime Data: 67% of UPI scams occur between 10 PM – 6 AM
  - MeitY Cybercrime Report 2023: Top scam keywords catalogued
  - RBI Circular RBI/2023-24/73: Social engineering fraud patterns
  - Indian elder fraud profile: NASSCOM + RBI joint study 2023
"""
import json
import os
import re
import math
from datetime import datetime, timedelta
from typing import Optional

import requests

# ── Real-life scam keywords (MeitY + RBI cybercrime report 2023) ──────────────
SCAM_KEYWORDS = {
    # Identity/Impersonation scams
    "kyc": ("KYC Update Scam", 35),
    "aadhaar": ("Aadhaar Fraud", 30),
    "pan card": ("PAN Card Scam", 30),
    "otp": ("OTP Phishing", 40),
    "share otp": ("OTP Phishing", 50),
    "verify account": ("Account Verification Scam", 35),
    "account suspend": ("Account Suspension Scam", 40),
    "account block": ("Account Block Scam", 40),
    "bank suspend": ("Fake Bank Alert", 45),

    # Authority impersonation
    "trai": ("TRAI Scam", 45),
    "telecom authority": ("TRAI Scam", 45),
    "income tax": ("IT Refund Scam", 35),
    "it refund": ("IT Refund Scam", 40),
    "irdai": ("Insurance Scam", 35),
    "sebi": ("Investment Scam", 35),
    "rbi": ("Fake RBI Alert", 45),
    "police": ("Police Impersonation", 40),
    "cbi": ("CBI Scam", 45),
    "enforcement": ("ED Scam", 45),

    # Prize / Lottery
    "prize": ("Prize/Lottery Scam", 40),
    "lottery": ("Lottery Scam", 45),
    "winner": ("Prize Scam", 35),
    "lucky draw": ("Lucky Draw Scam", 40),
    "reward": ("Fake Reward Scam", 25),

    # Urgency keywords
    "urgent": ("Urgency Pressure Scam", 20),
    "immediately": ("Urgency Pressure Scam", 20),
    "last chance": ("Urgency Scam", 30),
    "expire": ("Urgency Scam", 20),

    # Fake support
    "customer care": ("Fake Customer Support", 30),
    "helpline": ("Fake Helpline Scam", 25),
    "support team": ("Fake Support Scam", 25),
    "refund process": ("Fake Refund Scam", 35),
    "refund amount": ("Fake Refund Scam", 30),

    # Job / investment scams
    "work from home": ("Job Scam", 30),
    "earn daily": ("Investment Scam", 35),
    "guaranteed return": ("Investment Scam", 40),
    "double money": ("Ponzi Scam", 50),
    "investment plan": ("Investment Fraud", 25),

    # Electricity / utility scam (common in India 2023)
    "electricity bill": ("Electricity Bill Scam", 35),
    "disconnection": ("Utility Disconnection Scam", 35),
    "power cut": ("Utility Scam", 30),

    # Test/trick payment
    "test payment": ("Test Payment Trick", 30),
    "verification payment": ("Verification Payment Scam", 40),
    "registration fee": ("Advance Fee Scam", 30),
    "processing fee": ("Advance Fee Scam", 30),
    "token amount": ("Advance Fee Scam", 25),
}

# ── Known fraudulent UPI ID patterns (regex) ─────────────────────────────────
SUSPICIOUS_UPI_PATTERNS = [
    r"paytmcare\d+@",
    r"sbicare\d+@",
    r"support\d+@",
    r"helpdesk\d+@",
    r"customercare\d+@",
    r"refund\d+@",
    r"\d{10}@ybl",    # Random mobile@ybl without name
    r"kyc\w+@",
    r"prize\w+@",
    r"reward\w+@",
    r"income\w+@",
]

# ── Real RBI/NPCI statistical baselines ───────────────────────────────────────
# Source: RBI Annual Report 2023, NPCI Transaction Data
INDIA_AVG_LEGITIMATE_TXN = 3200.0      # ₹3,200 — NPCI reported avg UPI txn
INDIA_AVG_FRAUD_TXN = 48200.0          # ₹48,200 — RBI reported avg fraud amount
FRAUD_HOUR_START = 22                   # 10 PM
FRAUD_HOUR_END = 6                      # 6 AM (next day)
FRAUD_HOUR_PROBABILITY = 0.67           # 67% of UPI scams in this window

# Round amounts common in social engineering (₹500, ₹1000, etc.)
ROUND_AMOUNT_THRESHOLDS = [
    500, 1000, 2000, 5000, 10000, 15000, 20000, 25000, 50000, 75000, 100000, 150000, 200000
]


def analyze_transaction(
    org_id: int,
    amount: float,
    recipient_name: str,
    recipient_id: str = "",
    payment_method: str = "UPI",
    description: str = "",
    device_id: str = "",
    location: str = "",
    transaction_hour: Optional[int] = None,
    vulnerable_user: bool = False,
) -> dict:
    """
    Core fraud analysis engine.
    Returns a comprehensive risk assessment dict.
    """
    if transaction_hour is None:
        transaction_hour = datetime.utcnow().hour

    risk_score = 0
    flags = []
    explanations = []
    scam_kws = []

    # ── 1. Amount anomaly (calibrated to RBI data) ────────────────────────────
    amount_score, amount_flags, amount_expl = _check_amount_anomaly(org_id, amount, payment_method)
    risk_score += amount_score
    flags.extend(amount_flags)
    explanations.extend(amount_expl)

    # ── 2. New recipient detection ────────────────────────────────────────────
    is_new_recipient = _is_new_recipient(org_id, recipient_name, recipient_id)
    if is_new_recipient:
        risk_score += 30
        flags.append("NEW_RECIPIENT")
        explanations.append(f"First payment to '{recipient_name}' — no prior transaction history")

    # ── 3. Unusual timing (NPCI: 67% of fraud at 10PM–6AM) ───────────────────
    hour_score, hour_flags, hour_expl = _check_transaction_timing(transaction_hour)
    risk_score += hour_score
    flags.extend(hour_flags)
    explanations.extend(hour_expl)

    # ── 4. Round amount attack (social engineering hallmark) ──────────────────
    if _is_round_amount(amount):
        risk_score += 12
        flags.append("ROUND_AMOUNT")
        explanations.append(f"Exact round amount (₹{amount:,.0f}) — common in social engineering scams")

    # ── 5. Suspicious UPI ID pattern ─────────────────────────────────────────
    if recipient_id:
        upi_score, upi_flags, upi_expl = _check_upi_pattern(recipient_id)
        risk_score += upi_score
        flags.extend(upi_flags)
        explanations.extend(upi_expl)

    # ── 6. Scam keyword scan in description ──────────────────────────────────
    kw_score, kw_flags, kw_expl, found_kws = _scan_scam_keywords(description)
    risk_score += kw_score
    flags.extend(kw_flags)
    explanations.extend(kw_expl)
    scam_kws.extend(found_kws)

    # ── 7. High-value threshold (RBI fraud avg = ₹48,200) ────────────────────
    if amount > 40000 and is_new_recipient:
        risk_score += 20
        flags.append("HIGH_VALUE_NEW_RECIPIENT")
        explanations.append(f"High amount (₹{amount:,.0f}) to a new recipient — matches RBI fraud profile")

    if amount > 100000:
        risk_score += 15
        flags.append("VERY_HIGH_AMOUNT")
        explanations.append(f"₹{amount:,.0f} exceeds ₹1 lakh — RBI requires extra verification")

    # ── 8. Vulnerable user amplification ─────────────────────────────────────
    if vulnerable_user and risk_score >= 25:
        # Escalate risk score for vulnerable users (senior citizens)
        risk_score = min(100, int(risk_score * 1.25))
        flags.append("VULNERABLE_USER_ESCALATED")

    # ── Clamp and classify ────────────────────────────────────────────────────
    risk_score = min(100, max(0, risk_score))
    risk_level = _classify_risk(risk_score)

    # ── Trusted contact alert decision ────────────────────────────────────────
    should_alert_contact = risk_level == "HIGH"

    # ── Generate user-friendly summary ───────────────────────────────────────
    summary = _generate_summary(risk_level, risk_score, explanations, scam_kws, vulnerable_user)

    return {
        "risk_score": risk_score,
        "risk_level": risk_level,
        "flags": flags,
        "explanations": explanations,
        "scam_keywords_found": scam_kws,
        "summary": summary,
        "should_alert_contact": should_alert_contact,
        "action": _get_action(risk_level),
        "action_message": _get_action_message(risk_level, vulnerable_user),
        "is_new_recipient": is_new_recipient,
    }


def _check_amount_anomaly(org_id: int, amount: float, payment_method: str) -> tuple:
    """
    Compare against user's historical 90-day baseline.
    Falls back to RBI/NPCI national averages if insufficient data.
    """
    risk_score = 0
    flags = []
    explanations = []

    try:
        from app.models.shield import FraudTransaction
        from app.extensions import db
        from sqlalchemy import func

        cutoff = datetime.utcnow() - timedelta(days=90)
        historical = db.session.query(FraudTransaction.amount).filter(
            FraudTransaction.org_id == org_id,
            FraudTransaction.created_at >= cutoff,
            FraudTransaction.status.in_(["CONFIRMED", "PENDING"]),
            FraudTransaction.user_feedback != "fraud",
        ).all()

        amounts = [r[0] for r in historical if r[0] and r[0] > 0]

        if len(amounts) >= 5:
            mean = sum(amounts) / len(amounts)
            variance = sum((x - mean) ** 2 for x in amounts) / len(amounts)
            std = max(variance ** 0.5, mean * 0.1)  # floor at 10% of mean
            z_score = (amount - mean) / std

            if z_score > 4:
                risk_score += 35
                flags.append("EXTREME_AMOUNT_SPIKE")
                explanations.append(f"Amount is {z_score:.1f}× your standard deviation — extremely unusual ({amount/mean:.1f}× your average of ₹{mean:,.0f})")
            elif z_score > 2.5:
                risk_score += 25
                flags.append("HIGH_AMOUNT_SPIKE")
                explanations.append(f"Amount (₹{amount:,.0f}) is {amount/mean:.1f}× your typical transaction average of ₹{mean:,.0f}")
            elif z_score > 1.5:
                risk_score += 12
                flags.append("ELEVATED_AMOUNT")
                explanations.append(f"Amount (₹{amount:,.0f}) is higher than your usual transactions (avg: ₹{mean:,.0f})")
        else:
            # Fall back to national averages (RBI data)
            if amount > INDIA_AVG_FRAUD_TXN:
                risk_score += 30
                flags.append("ABOVE_NATIONAL_FRAUD_AVERAGE")
                explanations.append(f"₹{amount:,.0f} exceeds the RBI-reported average fraud transaction of ₹{INDIA_AVG_FRAUD_TXN:,.0f}")
            elif amount > INDIA_AVG_LEGITIMATE_TXN * 5:
                risk_score += 18
                flags.append("HIGH_COMPARED_TO_NATIONAL_AVG")
                explanations.append(f"₹{amount:,.0f} is {amount/INDIA_AVG_LEGITIMATE_TXN:.1f}× the national average UPI transaction of ₹{INDIA_AVG_LEGITIMATE_TXN:,.0f}")

    except Exception:
        # Minimal fallback
        if amount > INDIA_AVG_FRAUD_TXN:
            risk_score += 25
            flags.append("HIGH_AMOUNT")
            explanations.append(f"₹{amount:,.0f} exceeds the national average fraud transaction amount")

    return risk_score, flags, explanations


def _is_new_recipient(org_id: int, recipient_name: str, recipient_id: str) -> bool:
    """Check if this recipient has been paid in the last 30 days."""
    try:
        from app.models.shield import FraudTransaction
        from app.extensions import db

        cutoff = datetime.utcnow() - timedelta(days=30)
        name_lower = recipient_name.strip().lower()

        existing = db.session.query(FraudTransaction).filter(
            FraudTransaction.org_id == org_id,
            FraudTransaction.created_at >= cutoff,
            FraudTransaction.status != "CANCELLED",
        ).all()

        for txn in existing:
            if txn.recipient_name.strip().lower() == name_lower:
                return False
            if recipient_id and txn.recipient_id and txn.recipient_id.strip().lower() == recipient_id.strip().lower():
                return False
        return True
    except Exception:
        return True  # Assume new if we can't check


def _check_transaction_timing(hour: int) -> tuple:
    """NPCI data: 67% of UPI scams occur 10 PM – 6 AM."""
    risk_score = 0
    flags = []
    explanations = []

    if hour >= FRAUD_HOUR_START or hour < FRAUD_HOUR_END:
        risk_score += 22
        flags.append("UNUSUAL_HOUR")
        period = f"{hour}:00 AM" if hour < 12 else (f"12:00 PM" if hour == 12 else f"{hour-12}:00 PM")
        if hour >= 22:
            period = f"{hour}:00 PM"
        elif hour < 6:
            period = f"{hour}:00 AM"
        explanations.append(
            f"Transaction initiated at {hour:02d}:00 — NPCI data shows 67% of UPI frauds happen between 10 PM and 6 AM"
        )
    elif 6 <= hour < 8:
        risk_score += 8
        flags.append("EARLY_MORNING")
        explanations.append(f"Early morning transaction ({hour:02d}:00) — slightly elevated risk window")

    return risk_score, flags, explanations


def _is_round_amount(amount: float) -> bool:
    """Detect exactly round amounts used in social engineering."""
    for threshold in ROUND_AMOUNT_THRESHOLDS:
        if abs(amount - threshold) < 0.01:
            return True
    # Also check if amount is a multiple of 1000 above 5000
    if amount >= 5000 and amount % 1000 == 0:
        return True
    return False


def _check_upi_pattern(upi_id: str) -> tuple:
    """Detect suspicious UPI ID patterns matching known fraud templates."""
    risk_score = 0
    flags = []
    explanations = []

    upi_lower = upi_id.strip().lower()
    for pattern in SUSPICIOUS_UPI_PATTERNS:
        if re.search(pattern, upi_lower):
            risk_score += 30
            flags.append("SUSPICIOUS_UPI_ID")
            explanations.append(f"UPI ID '{upi_id}' matches a pattern associated with fake bank/support scams")
            break

    return risk_score, flags, explanations


def _scan_scam_keywords(description: str) -> tuple:
    """Scan transaction description for scam keyword matches (MeitY report 2023)."""
    risk_score = 0
    flags = []
    explanations = []
    found_kws = []

    if not description:
        return risk_score, flags, explanations, found_kws

    desc_lower = description.strip().lower()
    total_kw_score = 0
    categories_found = set()

    for keyword, (category, score) in SCAM_KEYWORDS.items():
        if keyword in desc_lower:
            total_kw_score = max(total_kw_score, score)  # Use highest score
            categories_found.add(category)
            found_kws.append(keyword)

    if categories_found:
        risk_score = min(50, total_kw_score)
        flags.append("SCAM_KEYWORDS_DETECTED")
        cat_list = ", ".join(list(categories_found)[:3])
        explanations.append(f"Description contains scam-associated keywords — possible {cat_list}")

    return risk_score, flags, explanations, found_kws


def _classify_risk(score: int) -> str:
    if score >= 70:
        return "HIGH"
    elif score >= 40:
        return "MEDIUM"
    return "LOW"


def _get_action(risk_level: str) -> str:
    return {
        "LOW": "ALLOW",
        "MEDIUM": "VERIFY",
        "HIGH": "HOLD",
    }.get(risk_level, "ALLOW")


def _get_action_message(risk_level: str, vulnerable_user: bool) -> str:
    if risk_level == "HIGH":
        if vulnerable_user:
            return "⚠️ THIS PAYMENT LOOKS DANGEROUS. Please call your family member or bank before sending any money."
        return "⚠️ High-risk transaction detected. This payment has been held for your protection. Please verify the recipient carefully before proceeding."
    elif risk_level == "MEDIUM":
        if vulnerable_user:
            return "⚠️ This payment is unusual. Please verify the recipient before continuing."
        return "This transaction looks unusual. Please confirm your identity with OTP before proceeding."
    else:
        return "Transaction looks safe. Proceeding normally."


def _generate_summary(risk_level: str, score: int, explanations: list, scam_kws: list, vulnerable_user: bool) -> str:
    if risk_level == "HIGH":
        reasons = " | ".join(explanations[:3])
        return f"🔴 HIGH RISK (Score: {score}/100) — {reasons}"
    elif risk_level == "MEDIUM":
        reasons = " | ".join(explanations[:2])
        return f"🟡 MEDIUM RISK (Score: {score}/100) — {reasons}"
    else:
        return f"🟢 LOW RISK (Score: {score}/100) — Transaction appears normal"


# ── Fraud Awareness Chatbot ───────────────────────────────────────────────────

CHATBOT_KNOWLEDGE = {
    "otp": {
        "response": (
            "🚨 NEVER share your OTP with anyone — not even bank employees!\n\n"
            "Real banks NEVER ask for OTP over phone or message. "
            "If someone is asking for your OTP, they are almost certainly a scammer. "
            "Hang up immediately and call your bank's official number (printed on your card/passbook).\n\n"
            "What to do: ① End the call ② Block the number ③ Report to cybercrime.gov.in or call 1930."
        ),
        "is_scam": True,
        "category": "OTP Phishing"
    },
    "kyc": {
        "response": (
            "🚨 This is a very common KYC Update Scam!\n\n"
            "Banks conduct KYC in-branch or through their official app — never by asking you to pay or share credentials over phone/WhatsApp. "
            "If someone claiming to be from SBI, Paytm, or any bank asks you to 'update KYC' by clicking a link or making a payment — it is fraud.\n\n"
            "What to do: ① Do NOT click any link ② Visit your bank branch physically ③ Report to 1930 (National Cybercrime Helpline)."
        ),
        "is_scam": True,
        "category": "KYC Scam"
    },
    "customer support": {
        "response": (
            "🚨 Fake customer support is a top fraud method in India!\n\n"
            "Scammers pose as bank/PayTM/NPCI support agents. Real support never asks you to: "
            "share OTP, install apps like AnyDesk or TeamViewer, make a 'test payment', or provide card details.\n\n"
            "Always find support numbers from the bank's official website, never from Google search results or WhatsApp."
        ),
        "is_scam": True,
        "category": "Fake Customer Support"
    },
    "prize": {
        "response": (
            "🚨 This is a Prize/Lottery Scam!\n\n"
            "You have NOT won a prize. This is one of the most common scams. "
            "Scammers ask for a small 'processing fee' to release your 'winnings' — there are no winnings. "
            "No legitimate lottery ever asks you to pay fees upfront.\n\n"
            "What to do: Block the sender/caller immediately. Report to cybercrime.gov.in."
        ),
        "is_scam": True,
        "category": "Prize/Lottery Scam"
    },
    "electricity": {
        "response": (
            "🚨 This sounds like the Electricity Disconnection Scam!\n\n"
            "Scammers send fake 'last warning' messages claiming your electricity will be cut and ask you to pay immediately via UPI. "
            "Real electricity boards send physical bills and official notices — they do NOT contact via WhatsApp or ask for immediate UPI payment.\n\n"
            "What to do: ① Check your official BESCOM/MSEDCL/TNEB app ② Call the official customer care ③ Never pay via a number/link in an SMS."
        ),
        "is_scam": True,
        "category": "Utility Bill Scam"
    },
    "transaction flagged": {
        "response": (
            "Your transaction was flagged by SmartShield because one or more risk signals were detected:\n\n"
            "🔴 HIGH RISK: New recipient + unusual amount or timing → Transaction held for safety\n"
            "🟡 MEDIUM RISK: Some unusual signals → OTP re-confirmation required\n"
            "🟢 LOW RISK: Normal → Proceeds automatically\n\n"
            "If you believe the flag was incorrect, you can confirm the transaction and the system learns. "
            "If you think it was a scam attempt, tap 'Cancel & Report'."
        ),
        "is_scam": False,
        "category": "System Explanation"
    },
    "safe payment": {
        "response": (
            "✅ Signs a payment request is likely safe:\n"
            "• You initiated the transaction (not responding to a call/message)\n"
            "• You've paid this person/merchant before\n"
            "• The amount matches an expected bill or purchase\n"
            "• The UPI ID is a recognizable business name\n\n"
            "🔴 Red flags to watch for:\n"
            "• Someone called/messaged YOU asking for payment\n"
            "• Urgency or threats (account block, legal action)\n"
            "• New payee with a large amount\n"
            "• 'Test payment' requests\n"
            "• Any mention of OTP, KYC, or remote access apps"
        ),
        "is_scam": False,
        "category": "Safety Guide"
    },
    "default": {
        "response": (
            "👋 I'm the SmartShield Fraud Assistant. I can help you:\n\n"
            "🔍 Understand why a transaction was flagged\n"
            "⚠️ Identify scam patterns (OTP fraud, KYC scam, lottery scam, etc.)\n"
            "✅ Know how to verify if a payment is safe\n"
            "🛡️ Get guidance on what to do if you've been scammed\n\n"
            "Try asking: 'Is this payment safe?', 'Someone asked for my OTP — what do I do?', "
            "'Why was my transaction held?', or 'I got a message about electricity disconnection'."
        ),
        "is_scam": False,
        "category": "General"
    }
}


def fraud_chatbot(query: str, org_id: int) -> dict:
    """
    Fraud awareness chatbot — first tries Gemini API, falls back to rule-based knowledge.
    """
    api_key = os.getenv("GEMINI_API_KEY", "")
    q_lower = query.strip().lower()

    # Try Gemini first
    if api_key and len(api_key) > 20:
        try:
            system_prompt = """You are SmartShield's Fraud Protection Assistant for Indian banking users.
You specialize in: UPI fraud, OTP scams, KYC fraud, fake customer support, lottery scams, social engineering.
Always give clear, actionable advice. Use simple language (the user may be a senior citizen).
Mention relevant Indian resources: cybercrime.gov.in, helpline 1930, bank's official numbers.
Keep responses under 200 words. Use emoji sparingly but effectively for warnings.
If the situation is a confirmed scam, say so clearly with 🚨. If unclear, explain how to verify."""

            payload = {
                "contents": [{"role": "user", "parts": [{"text": f"{system_prompt}\n\nUser query: {query}"}]}],
                "generationConfig": {"temperature": 0.4, "maxOutputTokens": 300}
            }
            resp = requests.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}",
                json=payload, timeout=10
            )
            if resp.status_code == 200:
                answer = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
                is_scam = any(w in q_lower for w in ["otp", "kyc", "prize", "lottery", "electricity", "scam", "fraud", "block", "suspend"])
                return {"response": answer, "is_scam_detected": is_scam, "scam_category": "AI Detected", "source": "gemini"}
        except Exception:
            pass

    # Rule-based fallback
    for keyword, data in CHATBOT_KNOWLEDGE.items():
        if keyword in q_lower:
            return {
                "response": data["response"],
                "is_scam_detected": data["is_scam"],
                "scam_category": data["category"],
                "source": "rule_based"
            }

    return {
        "response": CHATBOT_KNOWLEDGE["default"]["response"],
        "is_scam_detected": False,
        "scam_category": "General",
        "source": "rule_based"
    }


def send_trusted_contact_alert(contact_name: str, contact_email: str, contact_phone: str,
                                transaction: dict) -> bool:
    """
    Simulate trusted contact alert (in production: integrate SMS/email gateway).
    For demo: logs the alert and returns success.
    """
    try:
        alert_msg = (
            f"SmartShield Alert for {contact_name}:\n"
            f"A HIGH-RISK transaction of ₹{transaction.get('amount', 0):,.0f} "
            f"to '{transaction.get('recipient_name', 'Unknown')}' was detected and held.\n"
            f"Risk Score: {transaction.get('risk_score', 0)}/100\n"
            f"Reason: {', '.join(transaction.get('explanations', [])[:2])}\n"
            f"Please contact the account holder to verify."
        )
        # In production: send SMS via Twilio/MSG91, email via SendGrid
        # For demo: just log
        print(f"[SmartShield] Trusted contact alert sent to {contact_name}: {alert_msg}")
        return True
    except Exception:
        return False


def get_shield_stats(org_id: int) -> dict:
    """Get SmartShield dashboard statistics."""
    try:
        from app.models.shield import FraudTransaction
        from app.extensions import db
        from sqlalchemy import func

        total = db.session.query(func.count(FraudTransaction.id)).filter(
            FraudTransaction.org_id == org_id
        ).scalar() or 0

        high_risk_blocked = db.session.query(func.count(FraudTransaction.id)).filter(
            FraudTransaction.org_id == org_id,
            FraudTransaction.risk_level == "HIGH",
            FraudTransaction.status == "CANCELLED"
        ).scalar() or 0

        medium_risk = db.session.query(func.count(FraudTransaction.id)).filter(
            FraudTransaction.org_id == org_id,
            FraudTransaction.risk_level == "MEDIUM"
        ).scalar() or 0

        amount_protected = db.session.query(func.sum(FraudTransaction.amount)).filter(
            FraudTransaction.org_id == org_id,
            FraudTransaction.risk_level == "HIGH",
            FraudTransaction.status == "CANCELLED"
        ).scalar() or 0.0

        recent = db.session.query(FraudTransaction).filter(
            FraudTransaction.org_id == org_id
        ).order_by(FraudTransaction.created_at.desc()).limit(10).all()

        return {
            "total_analyzed": total,
            "high_risk_blocked": high_risk_blocked,
            "medium_risk_flagged": medium_risk,
            "amount_protected": round(amount_protected, 2),
            "recent_transactions": [t.to_dict() for t in recent],
        }
    except Exception as e:
        return {
            "total_analyzed": 0,
            "high_risk_blocked": 0,
            "medium_risk_flagged": 0,
            "amount_protected": 0.0,
            "recent_transactions": [],
        }
