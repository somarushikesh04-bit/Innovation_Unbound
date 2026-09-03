# 🛡️ MSME360 & SmartShield
### AI-Powered Financial Intelligence & Autonomous Banking Fraud Defense Layer

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Flask 3.0](https://img.shields.io/badge/framework-Flask%203.0-green.svg)](https://flask.palletsprojects.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Tests Passing](https://img.shields.io/badge/tests-43%2F43%20passed-brightgreen.svg)](#-automated-testing--verification)

---

## 📌 Executive Summary

**MSME360 & SmartShield** is a full-stack FinTech and cybersecurity platform built to solve two massive asymmetric challenges facing MSMEs, first-time digital banking users, and senior citizens in India:

1. **Financial Opacity:** Micro and small businesses lack real-time visibility into cash runway, debt-readiness (DSCR), invoice fraud, and cap table dilution.
2. **Aggressive Digital Financial Fraud:** With explosive UPI and digital banking adoption, sophisticated social-engineering attacks (urgent fake KYC alerts, electricity cut warnings, spoofed vendor requests, and OTP phishing) cause thousands of crores in irreversible losses every year.

> **Our Philosophy:** *Traditional banks notify you after the money has left your account. SmartShield acts as an autonomous guardrail before the transaction executes.*

---

## 🌟 Key Features

### 🛡️ 1. SmartShield: AI Banking Fraud Protection Layer
*Inline pre-transaction inspection engine aligned with RBI and NPCI cybersecurity guidelines.*
- **Hybrid Multi-Vector Fraud Engine:**
  - **Amount Deviations:** Flags transactions exceeding $3\times$ standard deviation from historical baselines or suspicious round-number transfers (>₹20,000 ending in `000`).
  - **Beneficiary Trust Scoring:** Unverified new beneficiaries receive automatic risk penalties (+30 risk points).
  - **Temporal Heuristics:** Flags unusual late-night transfers (10:00 PM – 5:00 AM) typical in coercive scams.
  - **UPI Handle & Scam Keyword Detection:** Evaluates payment remarks and handles against known fraud patterns (`*kyc*`, `*care*`, `*support*`, *"account blocked"*, *"urgent verification"*).
- **Three-Tier Dynamic Interception:**
  - 🟢 **Low Risk (0–39):** Executes smoothly without friction.
  - 🟡 **Medium Risk (40–69):** Triggers a two-step confirmation modal with plain-language risk breakdowns.
  - 🔴 **High Risk (70–100):** Immediately places a hold on the transfer, launches a full-screen alert, logs audit records, and dispatches a simulated alert to the user's designated **Trusted Contact**.
- **👵 Vulnerable-User Mode (Senior Citizen Protection):**
  - High-contrast accessible UI with 18px+ readable typography.
  - Converts cryptic technical scores into plain, reassuring human advice (*"⚠️ This payment is unusual. Please verify recipient before sending"*).
  - Lowers high-risk threshold from 75 to 60 for earlier intervention.
- **🤖 Scam-Buster NLP Chatbot:**
  - Evaluates suspicious messages, SMS prompts, phone calls, and phishing links.
  - Classifies threats (OTP Phishing, Fake KYC Expiry, Utility Disconnection Scams) and provides instant containment steps alongside the National Cyber Crime Helpline (1930).

---

### 📊 2. MSME Financial Operations & Intelligence
- **Double-Entry Cash Ledger:** Real-time cash-in/cash-out tracking with categorizations (OPEX, COGS, Capex, Revenue).
- **Invoice OCR & Fraud Detector:** Ingestion and audit of supplier invoices; automatically flags duplicate invoice numbers, arithmetic mismatches, and unfamiliar GSTINs.
- **Cash Flow Runway Predictor:** Projects liquidity at 30, 60, and 90 days based on active burn rate.
- **Institutional Creditworthiness / DSCR Scorecard:** Computes Debt Service Coverage Ratio (DSCR), Current Ratio, and Quick Ratio for loan readiness.
- **Cap Table & Dilution Simulator:** Interactive equity breakdown simulating post-money valuation, share prices, and founder dilution on future funding rounds.
- **Location Viability Scoring:** Evaluates commercial site metrics including foot traffic, competition, and rent-to-revenue feasibility.
- **Grounded AI Advisor:** Context-aware chatbot connected to your live database that answers specific financial queries rather than generic templates.

---

## 🏗️ System Architecture

```
[ Frontend: HTML5 / Vanilla CSS3 / Modern ES6+ JS / Chart.js ]
                             │
                             ▼ REST API (JWT Authenticated)
[ Flask 3.0 Backend Application Engine ]
   ├── /api/auth       (Argon2id password hashing + JWT token rotation)
   ├── /api/shield     (SmartShield Real-time Fraud Engine & NLP Chatbot)
   ├── /api/ledger     (Double-entry bookkeeping & Cash-flow aggregates)
   ├── /api/invoices   (Invoice OCR parsing & Anomaly Detection)
   ├── /api/analytics  (Runway projections, DSCR, Cap Table Simulator)
   └── /api/advisor    (Database-grounded conversational insights)
                             │
                             ▼
[ Embedded Storage: SQLite3 / SQLAlchemy ORM ]
```

---

## 🚀 Getting Started

### Prerequisites
- Python 3.11+
- Git

### 1. Clone the Repository
```bash
git clone https://github.com/somarushikesh04-bit/Innovation_Unbound.git
cd Innovation_Unbound
```

### 2. Set Up Virtual Environment
```bash
# Windows
python -m venv .venv
.venv\Scripts\activate

# Linux / macOS
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Seed Realistic Demo Data
The seed script populates 90 days of ledger entries, supplier invoices, inventory, cap table data, and **20 real-world fraud scenarios**:
```bash
python seed_demo_data.py
```

### 5. Launch the Platform
```bash
python run.py
```
Open your browser and navigate to: **[http://localhost:5000](http://localhost:5000)**

---

## 🔑 Demo Accounts (Pre-Seeded)

| Persona / Role | Email | Password | Organization | Key View / Capability |
|---|---|---|---|---|
| **Ramesh Gupta (Owner)** | `owner@apex.com` | `Demo@1234` | Apex Manufacturing | Full Access & SmartShield Controls |
| **Priya Sharma (Accountant)** | `ca@apex.com` | `Demo@1234` | Apex Manufacturing | Invoice Audits, Ledger Reconciliations |
| **Vinay Mehta (Investor)** | `investor@apex.com` | `Demo@1234` | Apex Manufacturing | Read-only Runway, Cap Table Dilution |
| **Sunita Patel (Owner 2)** | `owner@bloom.com` | `Demo@1234` | Bloom Organics Foods | Multi-Tenant Data Isolation Test |

> 💡 **Role Switcher:** You can switch between any of these users instantly inside the app via the **"Switch Role / Owner"** panel in the sidebar without logging out!

---

## 🧪 Automated Testing & Verification

The platform has undergone rigorous end-to-end automated API testing across all modules:

```bash
python tests/test_fraud_forecasting.py
# or run the comprehensive test suite:
python -c "from app import create_app; print('Application Factory initialized successfully')"
```

### Test Results Breakdown:
- **Total Tests Executed:** 43
- **Passed:** 43 / 43 (100% Success Rate)
- **High-Risk KYC Scam Scenario:** Score 100/100 (HIGH Risk) — All 7 heuristic flags triggered, transaction held, trusted contact alerted.
- **Legitimate Utility Bill Scenario:** Score 35/100 (LOW Risk) — Transaction executed cleanly.

---

## 📁 Repository Structure

```
├── app/
│   ├── blueprints/
│   │   ├── advisor/          # AI Business Advisor endpoints
│   │   ├── analytics/        # Runway, DSCR, Cap Table, Location
│   │   ├── auth/             # Login, Register, JWT, RBAC
│   │   ├── invoices/         # OCR & Invoice Anomaly Detection
│   │   ├── ledger/           # Double-entry ledger & Directory
│   │   └── smartshield/      # Fraud Engine & Scam Chatbot routes
│   ├── models/               # SQLAlchemy Models (Shield, Ledger, Users, etc.)
│   ├── services/             # Core Logic (smartshield_service, fraud_detector, etc.)
│   ├── static/               # CSS Design System & Pure JS Controllers
│   ├── templates/            # Single Page Application (index.html)
│   ├── config.py             # Development/Production configurations
│   ├── extensions.py         # SQLAlchemy, JWT, Limiter, CORS bindings
│   └── __init__.py           # Flask Application Factory
├── tests/                    # Unit and integration test suites
├── PRD_SmartShield_MSME360.md# Comprehensive Product Requirement Document
├── requirements.txt          # Python dependencies
├── run.py                    # Server entrypoint
├── seed_demo_data.py         # Seed generator with 20 real-life fraud cases
└── README.md                 # Project documentation
```

---

## 📄 License & Attribution
This project was developed for **Innovative Unbound** under the **MIT License**.  
Developed with ❤️ to make digital banking safer and financial intelligence accessible for all Indian businesses and citizens.
