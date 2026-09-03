# Product Requirement Document (PRD) & Detailed Technical Specification

## Project Title: **MSME360 & SmartShield**
**Sub-title:** AI-Powered Business Financial Intelligence & Autonomous Banking Fraud Defense Layer  
**Target Category:** FinTech / AI Security / Hackathon Project  
**Author:** Engineering & Product Team  
**Version:** 2.0 (Production / Demo Ready)  

---

## 1. Executive Summary

### 1.1 Problem Statement
MSMEs (Micro, Small, and Medium Enterprises), senior citizens, and first-time digital banking users face two critical asymmetric challenges:
1. **Financial Opacity:** Small businesses struggle with cash flow visibility, forecasting runway, evaluating creditworthiness for formal debt financing, and detecting supplier billing anomalies.
2. **Aggressive Digital Financial Fraud:** With India's explosive UPI and digital banking adoption, digital scams (fake KYC alerts, urgent payment requests, OTP social engineering, electricity disconnection threats, fake support handles) result in thousands of crores lost annually. Senior citizens and non-technical business founders are disproportionately vulnerable.

### 1.2 Solution Overview
**MSME360 & SmartShield** provides a unified platform combining:
- **Core MSME Financial Suite:** Automated double-entry ledger, Cash Flow Runway predictor (30/60/90 days), AI-driven Invoice Anomaly & Duplicate Detection, Location Viability Scoring, Cap Table & Dilution Simulator, and a Grounded AI Business Advisor.
- **SmartShield Banking Fraud Defense Layer:** An intelligent inline interception engine that screens transactions prior to execution, calculates real-time multi-dimensional risk scores (0–100), presents accessible high-impact warnings for vulnerable users, alerts trusted family contacts/approvers on high-risk holds, and provides an NLP-powered Scam Assessment Chatbot.

---

## 2. Product Personas & Target Users

| Persona | Description | Key Pain Points | Platform Solution |
|---|---|---|---|
| **Ramesh Gupta** *(Senior MSME Founder / Owner)* | 58 years old, runs Apex Manufacturing; traditional accounting background transitioning to digital payments. | High vulnerability to urgent supplier spoofing, complex financial reports, fear of digital scams. | Vulnerable-User Mode (high contrast, plain language warnings), automated Runway alerts, SmartShield instant hold. |
| **Priya Sharma** *(Chief Accountant)* | Oversees accounts payable, audits invoices, tracks reconciliations. | Fake/duplicate supplier invoices, irregular billing amounts, late reconciliation. | OCR Invoice Auditing with anomaly flags, detailed Ledger transaction breakdown, anomaly chips. |
| **Vinay Mehta** *(Angel / VC Investor)* | Board member or seed equity investor tracking financial runway. | Requires unvarnished visibility into cap table dilution, cash burn, and DSCR credit health. | Dedicated Investor View, Cap Table & Dilution Simulator, Read-only RBAC access. |
| **Anjali Gupta** *(Trusted Contact / Approver)* | Daughter of senior founder; designated secondary verification contact. | Worries about elderly parent falling for social-engineering traps while approving bank payments. | Automated simulated alert trigger whenever a transaction is held by SmartShield (>₹50,000 or High Risk). |

---

## 3. Core Modules & Feature Specifications

### Module 1: SmartShield — AI-Powered Fraud Defense
*Inline transaction risk inspection engine aligned with RBI & NPCI cybersecurity guidelines.*

1. **Hybrid Multi-Vector Risk Engine:**
   - **Amount Anomaly Scoring:** Compares incoming amount against historical average (₹5,000–₹15,000 baseline). Flags amounts exceeding $3\times$ std-dev or round psychological amounts (>₹20,000 ending in 000).
   - **Recipient Trust Verification:** Tracks whether recipient is verified in the address book or is a newly created beneficiary. High-value new recipients automatically add +30 risk points.
   - **Vulnerability / Heuristic Temporal Rules:** Flags late-night transactions (10:00 PM – 5:00 AM) typical in coerced or distressed transfers.
   - **UPI / Beneficiary Heuristics:** Matches against known fraud identifier regexes (e.g., `*care*`, `*kyc*`, `*support*`, `*sbi*` on non-bank merchant handles).
   - **Social-Engineering & Urgent Keyword Detection:** Scans payment remarks/memos for urgent coercive terms: *"KYC urgent"*, *"account blocked"*, *"customs release"*, *"lottery"*, *"electricity cut"*.
2. **Three-Tier Action Flow:**
   - **🟢 Low Risk (0–39):** Proceeds immediately without friction.
   - **🟡 Medium Risk (40–69):** Requires explicit two-step modal confirmation, displaying plain-language risk factors.
   - **🔴 High Risk (70–100):** Immediate transaction hold; full-screen blocking modal; notification dispatched to designated Trusted Contact; mandatory cooling-off period / secondary verification.
3. **Vulnerable-User Mode (Senior Citizen Protection):**
   - High-contrast banner toggle on the UI.
   - Enlarges typography to 18px+, converts technical risk codes into clear human advice (*"⚠️ This payment is unusual. Please verify recipient before sending."*).
   - Lowers high-risk threshold from 75 to 60 for earlier intervention.
4. **Scam Buster NLP Chatbot:**
   - Evaluates suspicious messages, SMS prompts, phone calls, and phishing links.
   - Classifies threats into: OTP Phishing, Fake KYC Expiry, Utility/Electricity Scams, Impersonation Support Scams.
   - Returns structured actionable advice, emergency helpline (1930 / cybercrime.gov.in), and step-by-step containment instructions.

---

### Module 2: Financial Operations & Ledger
1. **Double-Entry Cash Ledger:**
   - Tracks cash-in (Revenue, Receivables) vs. cash-out (OPEX, COGS, Capex).
   - Live summary computations: Net Cash Flow, Burn Rate, Aggregate Balances.
2. **Invoice OCR & Fraud Detector:**
   - Ingestion of invoices with automated parsing.
   - Flags duplicate invoice numbers, mismatch in line-item sums vs total, sudden spikes in vendor rates, and unfamiliar GSTINs.
3. **Enterprise Directory & Inventory:**
   - Verified supplier and customer directory with transaction histories.
   - Inventory tracking with reorder thresholds and low-stock indicators.

---

### Module 3: Strategic Analytics & Capital Engine
1. **Cash Flow Runway Predictor:**
   - Calculates daily burn rate and projects cash positions at 30, 60, and 90 days.
   - Alerts on zero-cash horizon date.
2. **DSCR & Creditworthiness Calculator:**
   - Calculates Debt Service Coverage Ratio (DSCR), Current Ratio, Quick Ratio, and Gross Margins.
   - Generates an institutional-grade loan readiness scorecard for formal banking credit.
3. **Cap Table & Dilution Simulator:**
   - Visualizes founder equity, investor stakes, and option pools.
   - Interactive simulator showing post-money valuation, share price, and founder dilution on new funding rounds.
4. **Location Intelligence:**
   - Evaluates commercial sites based on foot traffic, competition density, rent-to-revenue ratio, and logistical accessibility.

---

### Module 4: Grounded AI Business Advisor
1. **Role-Aware Chatbot:**
   - Reads directly from active database context (current cash, monthly burn, runway days, flagged invoices).
   - Delivers grounded financial counsel rather than generic boilerplate.

---

## 4. Technical Architecture & Tech Stack

```
[ Frontend: HTML5 / CSS3 / ES6+ JS / Chart.js ]
                        |
                        | REST API (JWT Authenticated)
                        v
[ Flask 3.0 Backend Application Engine ]
   ├── /api/auth       (Argon2id + JWT token issuance)
   ├── /api/shield     (SmartShield Fraud Inspection Engine)
   ├── /api/ledger     (Double-entry bookkeeping)
   ├── /api/invoices   (OCR & Invoice Auditing)
   ├── /api/analytics  (Runway, DSCR, Cap Table)
   └── /api/advisor    (Grounded Financial Insights)
                        |
                        v
[ Storage: SQLite3 / SQLAlchemy ORM ]
```

### 4.1 Component Breakdown
- **Frontend:** Pure Vanilla HTML5, CSS3 Custom Properties (Design System tokens), Modern JavaScript ES6+ (Fetch API, Chart.js, dynamic DOM routing, modal dialogs). Zero dependency on heavy node build pipelines.
- **Backend:** Python 3.11+ / Flask 3.0 (Application Factory pattern, Blueprints for modular domains).
- **Security & Cryptography:** 
  - `argon2-cffi` for state-of-the-art password hashing.
  - `Flask-JWT-Extended` with access & refresh token rotation.
  - `Flask-Limiter` for DoS/brute-force defense.
- **Database:** SQLite3 for lightweight embedded local operations, portable to PostgreSQL for enterprise production.

---

## 5. REST API Specifications

| Method | Endpoint | Description | Auth Required |
|---|---|---|---|
| `POST` | `/api/auth/login` | Authenticate user, issue JWT token & user profile | No |
| `GET` | `/api/auth/me` | Fetch active user, role, and tenant metadata | Yes |
| `GET` | `/api/shield/stats` | High-level metrics (Analyzed, Blocked, Amount Protected) | Yes |
| `POST` | `/api/shield/analyze` | Real-time fraud scoring for pending transaction | Yes |
| `POST` | `/api/shield/confirm/<id>` | User overrides/approves a held transaction | Yes |
| `POST` | `/api/shield/cancel/<id>` | User cancels a held fraudulent transaction | Yes |
| `GET` | `/api/shield/history` | Historical audit log of flagged/analyzed transactions | Yes |
| `GET/POST` | `/api/shield/trusted-contact` | View or configure designated approver / emergency contact | Yes |
| `POST` | `/api/shield/chatbot` | NLP Scam analysis query endpoint | Yes |
| `GET` | `/api/analytics/dashboard` | Consolidated KPIs, burn rate, health score | Yes |
| `GET` | `/api/analytics/runway` | 30/60/90 day projected cash runway | Yes |
| `GET` | `/api/ledger/entries` | Cash-in and cash-out entries | Yes |
| `POST` | `/api/advisor/chat` | Context-grounded conversational financial assistance | Yes |

---

## 6. Verification & Test Metrics

The solution has been exhaustively tested with end-to-end automated suites:
- **Total Test Cases Executed:** 43
- **Passed:** 43 / 43 (100% Success Rate)
- **High-Risk KYC Scam Test Scenario:**
  - Input: ₹95,000, recipient: `Fake SBI KYC Team`, handle: `sbicare9821@paytm`, hour: 23:00.
  - Engine Result: **Score: 100/100 (HIGH Risk)**.
  - Flags Triggered: `ELEVATED_AMOUNT`, `NEW_RECIPIENT`, `UNUSUAL_HOUR`, `ROUND_AMOUNT`, `SUSPICIOUS_UPI_ID`, `SCAM_KEYWORDS_DETECTED`, `HIGH_VALUE_NEW_RECIPIENT`.
  - Action: Held, Modal triggered, Contact notification alert logged.
- **Legitimate Utility Test Scenario:**
  - Input: ₹3,200, recipient: `Maharashtra Electricity Board`, hour: 11:00 AM.
  - Engine Result: **Score: 35/100 (LOW Risk)**.
  - Action: Cleared for execution immediately.

---

## 7. Hackathon Presentation & Pitch Framework

### 30-Second Elevator Pitch
> *"Traditional banking platforms wait until fraud occurs to alert users or file dispute reports. MSME360 with SmartShield changes the game: we act as an autonomous protective layer right before the money leaves the account. Designed specifically for vulnerable MSME owners and senior citizens, our explainable AI calculates risk in milliseconds, offers large plain-language guidance, and loops in trusted family members before life savings or company payroll are stolen."*

### Key Demo Highlights for Judges
1. **Live Owner Switcher:** Switch between Owner, Accountant, and Investor with one click in the sidebar to prove enterprise RBAC.
2. **Interactive Scam Simulation:** Click the *"🔴 KYC Scam"* demo chip, run analysis, and watch the high-risk hold modal trigger along with real-time trusted contact dispatch.
3. **Vulnerable-User Mode:** Toggle on senior mode to show large-text simplified explanations (*"⚠️ This payment is unusual. Please verify recipient before continuing"*).
4. **Context-Aware Business Advisor:** Ask *"What is my cash runway?"* and receive real-time answers calculated directly from the live ledger database.
