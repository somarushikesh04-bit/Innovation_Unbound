# 🛡️ MSME360 & SmartShield
### Autonomous Banking Fraud Protection & Financial Intelligence Platform

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![Flask 3.0](https://img.shields.io/badge/framework-Flask%203.0-green.svg)](https://flask.palletsprojects.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## 📌 Overview

**MSME360 & SmartShield** is an AI-powered financial operating system and real-time transaction defense layer. It is built to protect small businesses, senior citizens, and first-time digital banking users against financial opacity and digital fraud (urgent KYC scams, fake utility alerts, and social-engineering traps).

Unlike traditional banking systems that notify users **after** money has left their account, **SmartShield evaluates risk and intercepts fraudulent transfers before execution.**

---

## 🌟 Key Capabilities

### 🛡️ SmartShield: Real-Time Fraud Defense
- **Inline Risk Scoring (0–100):** Analyzes transaction amount anomalies ($>3\times$ baseline), beneficiary verification status, unusual hours (late-night coercion), and scam keywords (*"KYC urgent"*, *"account locked"*).
- **Three-Tier Action Layer:**
  - 🟢 **Low Risk (0–39):** Executes smoothly without friction.
  - 🟡 **Medium Risk (40–69):** Triggers a two-step confirmation modal with risk breakdown.
  - 🔴 **High Risk (70–100):** Automatically places a hold on the transfer, launches a blocking alert, and alerts a designated **Trusted Family Contact / Approver**.
- **👵 Vulnerable-User Mode:** Senior-friendly interface with high-contrast, large typography, and plain-language guidance (*"⚠️ This payment is unusual. Please verify the recipient before continuing"*).
- **🤖 Scam-Buster Chatbot:** Evaluates suspicious SMS, WhatsApp, and call requests to identify phishing patterns and provide immediate guidance (National Cybercrime Helpline 1930).

### 📊 MSME Financial Intelligence
- **Cash Flow Runway Predictor:** Projects 30/60/90-day cash liquidity based on active daily burn rate.
- **Invoice OCR & Fraud Detection:** Ingests supplier bills, identifying arithmetic mismatches, duplicate invoices, and suspicious GSTINs.
- **DSCR & Credit Health Scorecard:** Calculates loan-readiness metrics for formal bank debt financing.
- **Cap Table & Dilution Simulator:** Models equity distribution and dilution on future funding rounds.
- **AI Business Advisor:** Context-aware assistant grounded directly in live business financial data.

---

## 🏗️ Architecture

```
[ Frontend: HTML5 / CSS3 / Vanilla JavaScript / Chart.js ]
                             │
                             ▼ REST API (JWT Authenticated)
[ Flask 3.0 Backend Engine ]
   ├── Authentication & Role-Based Access Control (RBAC)
   ├── SmartShield Real-time Fraud Engine & NLP Chatbot
   ├── Double-Entry Cash Ledger & Aggregates
   ├── Invoice OCR & Anomaly Verification
   └── Strategic Analytics (Runway, DSCR, Cap Table)
                             │
                             ▼
[ Database: SQLAlchemy ORM / SQLite3 / PostgreSQL-ready ]
```

---

## 🚀 Quickstart Guide

### 1. Clone & Setup
```bash
git clone https://github.com/somarushikesh04-bit/Innovation_Unbound.git
cd Innovation_Unbound

# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate   # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Seed Realistic Demo Data
Populates 90 days of transactions, supplier invoices, inventory, and 20 real-world fraud scenarios:
```bash
python seed_demo_data.py
```

### 3. Run Application
```bash
python run.py
```
Open the port shown in the terminal in your browser.

---

## 🔑 Pre-Seeded Demo Profiles

| Role | Email | Password | Purpose |
|---|---|---|---|
| **Business Owner** | `owner@apex.com` | `Demo@1234` | Full access, financial controls & SmartShield |
| **Accountant** | `ca@apex.com` | `Demo@1234` | Invoice audit & ledger reconciliation |
| **Investor** | `investor@apex.com` | `Demo@1234` | Read-only runway & cap table visibility |
| **Second Tenant** | `owner@bloom.com` | `Demo@1234` | Multi-tenant data isolation test |

> 💡 **Quick Role Switcher:** Switch between any user role instantly via the sidebar panel without having to log out.

---

## 🧪 Verification
The platform includes an automated test suite covering authentication, ledger operations, invoice auditing, runway forecasting, and fraud prevention scenarios:
```bash
python -m pytest tests/
```

---

## 📄 License
Released under the [MIT License](LICENSE).
