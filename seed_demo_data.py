"""
Seed script: Populates MSME360 with realistic demo data for
Apex Manufacturing & Retail Pvt Ltd — 90 days of transactions,
invoices (including flagged anomalies), inventory, contacts, and cap table.
"""
import os
import sys
import random
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.extensions import db
from app.models.tenant import Tenant
from app.models.user import User, UserRole
from app.models.ledger import LedgerEntry, EntryType, EntryCategory
from app.models.invoice import Invoice, CapTableEntry
from app.models.directory import CustomerSupplier, InventoryItem

app = create_app("development")

CATEGORIES_DEBIT = [EntryCategory.OPEX.value, EntryCategory.COGS.value, EntryCategory.LIABILITY.value]
CATEGORIES_CREDIT = [EntryCategory.SALES_CASH.value, EntryCategory.SALES_CREDIT.value, EntryCategory.RECEIVABLE.value]


def run():
    with app.app_context():
        db.create_all()

        # Clear existing demo data
        print("Resetting demo data...")
        for model in [CapTableEntry, Invoice, InventoryItem, CustomerSupplier, LedgerEntry, User, Tenant]:
            db.session.query(model).delete()
        db.session.commit()

        # ── Tenants ────────────────────────────────────────────────────────────
        from argon2 import PasswordHasher
        ph = PasswordHasher()

        tenant1 = Tenant(name="Apex Manufacturing & Retail Pvt Ltd", slug="apex-manufacturing", currency="INR")
        tenant2 = Tenant(name="Bloom Organics Foods", slug="bloom-organics", currency="INR")
        db.session.add_all([tenant1, tenant2])
        db.session.flush()

        # ── Users ──────────────────────────────────────────────────────────────
        users = [
            User(org_id=tenant1.id, email="owner@apex.com", password_hash=ph.hash("Demo@1234"),
                 full_name="Ramesh Gupta", role=UserRole.OWNER.value),
            User(org_id=tenant1.id, email="ca@apex.com", password_hash=ph.hash("Demo@1234"),
                 full_name="Priya Sharma", role=UserRole.ACCOUNTANT.value),
            User(org_id=tenant1.id, email="staff@apex.com", password_hash=ph.hash("Demo@1234"),
                 full_name="Dinesh Kumar", role=UserRole.STAFF.value),
            User(org_id=tenant1.id, email="investor@apex.com", password_hash=ph.hash("Demo@1234"),
                 full_name="Vinay Mehta", role=UserRole.VIEWER.value),
            User(org_id=tenant2.id, email="owner@bloom.com", password_hash=ph.hash("Demo@1234"),
                 full_name="Sunita Patel", role=UserRole.OWNER.value),
        ]
        db.session.add_all(users)
        db.session.flush()

        owner = users[0]
        t1_id = tenant1.id

        # ── Ledger Entries — 90 days ───────────────────────────────────────────
        print("Creating 90 days of ledger entries...")
        today = date.today()
        random.seed(42)

        for day_offset in range(90, 0, -1):
            ref_date = today - timedelta(days=day_offset)

            # Daily revenue (trending upward)
            base_rev = 45000 + (day_offset * 100)
            rev = base_rev + random.randint(-8000, 12000)
            db.session.add(LedgerEntry(org_id=t1_id, entry_type=EntryType.CREDIT.value,
                category=EntryCategory.SALES_CASH.value, amount=rev,
                description="Daily cash sales", reference_date=ref_date))

            # Credit sales (receivables) every 3 days
            if day_offset % 3 == 0:
                cr_rev = random.randint(15000, 35000)
                db.session.add(LedgerEntry(org_id=t1_id, entry_type=EntryType.CREDIT.value,
                    category=EntryCategory.SALES_CREDIT.value, amount=cr_rev,
                    description="Credit sale to distributor", reference_date=ref_date))

            # COGS
            cogs = rev * random.uniform(0.38, 0.48)
            db.session.add(LedgerEntry(org_id=t1_id, entry_type=EntryType.DEBIT.value,
                category=EntryCategory.COGS.value, amount=round(cogs, 2),
                description="Raw material & production cost", reference_date=ref_date))

            # OPEX (rent, utilities, salaries weekly)
            if day_offset % 7 == 0:
                for desc, amt in [("Monthly rent", 45000), ("Salaries", 120000), ("Utilities", 12000)]:
                    db.session.add(LedgerEntry(org_id=t1_id, entry_type=EntryType.DEBIT.value,
                        category=EntryCategory.OPEX.value, amount=amt,
                        description=desc, reference_date=ref_date))

            # Smaller daily OPEX
            misc_opex = random.randint(2000, 6000)
            db.session.add(LedgerEntry(org_id=t1_id, entry_type=EntryType.DEBIT.value,
                category=EntryCategory.OPEX.value, amount=misc_opex,
                description="Miscellaneous operating expense", reference_date=ref_date))

        db.session.commit()

        # ── Contacts: Customers & Suppliers ──────────────────────────────────
        print("Creating contacts...")
        contacts = [
            CustomerSupplier(org_id=t1_id, entity_type="SUPPLIER", name="IndoSteel Corp",
                gstin="27AABCI1234D1Z5", payment_terms_days=45, outstanding_balance=185000),
            CustomerSupplier(org_id=t1_id, entity_type="SUPPLIER", name="Global Polymers Ltd",
                gstin="06AABCP5678E2Z3", payment_terms_days=30, outstanding_balance=92000),
            CustomerSupplier(org_id=t1_id, entity_type="SUPPLIER", name="Shree Logistics",
                gstin="INVALID-GSTIN", payment_terms_days=15, outstanding_balance=24000),
            CustomerSupplier(org_id=t1_id, entity_type="CUSTOMER", name="Metro Distributors",
                gstin="27AAACM9012F3Z7", payment_terms_days=30, outstanding_balance=267000,
                settlement_speed_score=7.5),
            CustomerSupplier(org_id=t1_id, entity_type="CUSTOMER", name="Bharat Retail Chain",
                gstin="09AAACB3456G4Z2", payment_terms_days=45, outstanding_balance=134500,
                settlement_speed_score=4.2),
        ]
        db.session.add_all(contacts)

        # ── Inventory ─────────────────────────────────────────────────────────
        print("Creating inventory...")
        inventory = [
            InventoryItem(org_id=t1_id, sku="SKU-001", name="Steel Rods (6mm)",
                unit_volume=1200, unit_cost=85.0, selling_price=120.0, reorder_threshold=200),
            InventoryItem(org_id=t1_id, sku="SKU-002", name="PVC Granules (Premium)",
                unit_volume=450, unit_cost=142.0, selling_price=198.0, reorder_threshold=100),
            InventoryItem(org_id=t1_id, sku="SKU-003", name="Packaging Boxes (Large)",
                unit_volume=8, unit_cost=45.0, selling_price=70.0, reorder_threshold=50),  # LOW STOCK
            InventoryItem(org_id=t1_id, sku="SKU-004", name="Adhesive Tape (Industrial)",
                unit_volume=12, unit_cost=22.0, selling_price=35.0, reorder_threshold=50),  # LOW STOCK
            InventoryItem(org_id=t1_id, sku="SKU-005", name="Polypropylene Sheet",
                unit_volume=620, unit_cost=215.0, selling_price=290.0, reorder_threshold=80),
        ]
        db.session.add_all(inventory)

        # ── Invoices ──────────────────────────────────────────────────────────
        print("Creating invoices with anomaly cases...")
        invoices = [
            # Normal, verified invoices
            Invoice(org_id=t1_id, invoice_number="INV-2024-001", vendor_name="IndoSteel Corp",
                vendor_gstin="27AABCI1234D1Z5", invoice_date=today - timedelta(days=15),
                subtotal=148305.08, tax_amount=26694.92, total_amount=175000.0,
                status="VERIFIED", anomaly_flags_json="[]",
                line_items_json='[{"description":"Steel Rods 6mm x 1000 units","amount":148305.08}]'),
            Invoice(org_id=t1_id, invoice_number="INV-2024-002", vendor_name="Global Polymers Ltd",
                vendor_gstin="06AABCP5678E2Z3", invoice_date=today - timedelta(days=10),
                subtotal=76271.19, tax_amount=13728.81, total_amount=90000.0,
                status="VERIFIED", anomaly_flags_json="[]",
                line_items_json='[{"description":"PVC Granules 500kg","amount":76271.19}]'),
            # FLAGGED: Tax math discrepancy
            Invoice(org_id=t1_id, invoice_number="INV-2024-042", vendor_name="Shree Logistics",
                vendor_gstin="INVALID-GSTIN", invoice_date=today - timedelta(days=5),
                subtotal=42000.0, tax_amount=9800.0, total_amount=54000.0,  # Should be 51800
                status="FLAGGED",
                anomaly_flags_json='[{"type":"TAX_MATH_DISCREPANCY","severity":"HIGH","message":"Subtotal (42000) + Tax (9800) = 51800, but total is 54000.","confidence":0.99},{"type":"INVALID_GSTIN_FORMAT","severity":"LOW","message":"GSTIN INVALID-GSTIN does not match standard format.","confidence":0.95}]',
                line_items_json='[{"description":"Freight charges Q3","amount":42000}]'),
            # FLAGGED: Duplicate invoice
            Invoice(org_id=t1_id, invoice_number="INV-2024-043", vendor_name="IndoSteel Corp",
                vendor_gstin="27AABCI1234D1Z5", invoice_date=today - timedelta(days=3),
                subtotal=148305.08, tax_amount=26694.92, total_amount=175000.0,
                status="FLAGGED",
                anomaly_flags_json='[{"type":"DUPLICATE_AMOUNT_DATE_WINDOW","severity":"MEDIUM","message":"Similar amount 175000 from IndoSteel Corp within 7 days (ID: 1).","confidence":0.82}]',
                line_items_json='[{"description":"Steel Rods 6mm x 1000 units","amount":148305.08}]'),
            # Pending
            Invoice(org_id=t1_id, invoice_number="INV-2024-044", vendor_name="Global Polymers Ltd",
                vendor_gstin="06AABCP5678E2Z3", invoice_date=today - timedelta(days=1),
                subtotal=50847.46, tax_amount=9152.54, total_amount=60000.0,
                status="PENDING", anomaly_flags_json="[]",
                line_items_json='[{"description":"PVC Granules 350kg","amount":50847.46}]'),
        ]
        db.session.add_all(invoices)

        # ── Cap Table ─────────────────────────────────────────────────────────
        print("Creating cap table...")
        cap = [
            CapTableEntry(org_id=t1_id, stakeholder_name="Ramesh Gupta (Founder)",
                stakeholder_type="FOUNDER", equity_percentage=55.0, shares_count=550000,
                invested_amount=500000, round_name="Incorporation"),
            CapTableEntry(org_id=t1_id, stakeholder_name="Anjali Gupta (Co-founder)",
                stakeholder_type="FOUNDER", equity_percentage=25.0, shares_count=250000,
                invested_amount=200000, round_name="Incorporation"),
            CapTableEntry(org_id=t1_id, stakeholder_name="Vinay Mehta (Angel Investor)",
                stakeholder_type="INVESTOR", equity_percentage=15.0, shares_count=150000,
                invested_amount=2000000, round_name="Seed"),
            CapTableEntry(org_id=t1_id, stakeholder_name="ESOP Pool",
                stakeholder_type="POOL", equity_percentage=5.0, shares_count=50000,
                invested_amount=0, round_name="Seed"),
        ]
        db.session.add_all(cap)

        db.session.commit()
        print("\n[OK] Demo data seeded successfully!")
        print("\n  Login credentials:")
        print("  Owner      -> owner@apex.com / Demo@1234")
        print("  Accountant -> ca@apex.com / Demo@1234")
        print("  Staff      -> staff@apex.com / Demo@1234")
        print("  Investor   -> investor@apex.com / Demo@1234")



def seed_smartshield(app_instance):
    """Seed SmartShield with 20 realistic Indian banking fraud scenarios."""
    import json
    from datetime import datetime, timedelta
    from app.models.shield import FraudTransaction, TrustedContact, ScamReport

    with app_instance.app_context():
        from app.extensions import db
        from app.models.tenant import Tenant
        from app.models.user import User

        db.session.query(ScamReport).delete()
        db.session.query(FraudTransaction).delete()
        db.session.query(TrustedContact).delete()
        db.session.commit()

        tenant = Tenant.query.filter_by(slug="apex-manufacturing").first()
        user = User.query.filter_by(email="owner@apex.com").first()
        if not tenant or not user:
            print("  [Shield] Demo tenant not found.")
            return

        now = datetime.utcnow()

        tc = TrustedContact(
            org_id=tenant.id, user_id=user.id,
            contact_name="Anjali Gupta (Daughter)",
            contact_phone="+91 98765 43210",
            contact_email="anjali.gupta@gmail.com",
            consent_given=True, is_active=True,
        )
        db.session.add(tc)

        scenarios = [
            (1, 23, 95000, "Fake SBI KYC Team", "sbicare9821@paytm", "UPI",
             "SBI KYC Update process urgent", 88, "HIGH", "CANCELLED",
             ["NEW_RECIPIENT","UNUSUAL_HOUR","HIGH_VALUE_NEW_RECIPIENT","SCAM_KEYWORDS_DETECTED","SUSPICIOUS_UPI_ID"],
             ["First payment to Fake SBI KYC Team","Transaction at 11 PM","Matches RBI fraud profile","Scam keywords found","Fake bank UPI ID"],
             ["kyc","urgent"], "fraud"),
            (3, 2, 50000, "Lucky Draw Prize Processing", "prize.winner2024@ybl", "UPI",
             "Congratulations! Claim your prize. Pay processing fee.", 92, "HIGH", "CANCELLED",
             ["NEW_RECIPIENT","UNUSUAL_HOUR","ROUND_AMOUNT","SCAM_KEYWORDS_DETECTED","SUSPICIOUS_UPI_ID"],
             ["Unknown recipient","2 AM highest risk window","Round amount social engineering","Prize Lottery Scam","Suspicious UPI ID"],
             ["prize","winner","lottery"], "fraud"),
            (5, 0, 75000, "Income Tax Refund Dept", "incometaxrefund@upi", "UPI",
             "Income tax refund processing fee urgent payment", 85, "HIGH", "CANCELLED",
             ["NEW_RECIPIENT","UNUSUAL_HOUR","ROUND_AMOUNT","SCAM_KEYWORDS_DETECTED"],
             ["New recipient","Midnight transaction","Round amount","IT Refund Scam keywords"],
             ["income tax","urgent","processing fee"], "fraud"),
            (7, 22, 48000, "Paytm Customer Helpline", "paytmcare0012@paytm", "UPI",
             "Refund amount customer care helpline verification", 82, "HIGH", "CANCELLED",
             ["NEW_RECIPIENT","UNUSUAL_HOUR","ABOVE_NATIONAL_FRAUD_AVERAGE","SCAM_KEYWORDS_DETECTED","SUSPICIOUS_UPI_ID"],
             ["New recipient","10 PM peak fraud window","Matches RBI avg fraud amount","Fake support keywords","Fake helpline UPI"],
             ["customer care","refund amount","helpline"], "fraud"),
            (10, 3, 100000, "TRAI Disconnection Notice", "trai.authority@upi", "NEFT",
             "TRAI notice: Pay immediately to avoid mobile suspension", 91, "HIGH", "CANCELLED",
             ["NEW_RECIPIENT","UNUSUAL_HOUR","VERY_HIGH_AMOUNT","ROUND_AMOUNT","SCAM_KEYWORDS_DETECTED"],
             ["Unknown TRAI contact","3 AM","Above 1L requires verification","Round amount","Authority Impersonation"],
             ["trai","account suspend"], "fraud"),
            (14, 1, 25000, "Electricity Board Emergency", "electricityboard.maha@ybl", "UPI",
             "Pay immediately electricity disconnection last warning", 78, "HIGH", "CANCELLED",
             ["NEW_RECIPIENT","UNUSUAL_HOUR","ROUND_AMOUNT","SCAM_KEYWORDS_DETECTED"],
             ["New electricity contact","1 AM risk window","Unrealistically high electricity bill","Utility Scam"],
             ["electricity bill","disconnection","last chance"], "fraud"),
            (18, 4, 15000, "Work From Home Jobs", "earnmore.daily@upi", "UPI",
             "Registration fee work from home daily earn guaranteed return", 80, "HIGH", "CANCELLED",
             ["NEW_RECIPIENT","UNUSUAL_HOUR","SCAM_KEYWORDS_DETECTED"],
             ["Unknown job portal","4 AM","Work-from-home Job Scam keywords"],
             ["work from home","earn daily","registration fee"], "fraud"),
            (20, 10, 85000, "Sunrise Steel Suppliers", "sunrisesteel@hdfcbank", "RTGS",
             "Steel coil purchase order SS-2024-891", 72, "HIGH", "CONFIRMED",
             ["NEW_RECIPIENT","HIGH_VALUE_NEW_RECIPIENT"],
             ["First payment to this supplier","High value new supplier user verified"],
             [], "legit"),
            (2, 14, 12000, "Rahul Sharma New Vendor", "rahulsharma.vendor@oksbi", "UPI",
             "Raw material advance payment", 48, "MEDIUM", "CONFIRMED",
             ["NEW_RECIPIENT","ELEVATED_AMOUNT"],["First payment to Rahul Sharma","Amount above typical"],
             [], "legit"),
            (4, 9, 8500, "Prakash Electricals", "prakash.elec@upi", "UPI",
             "Electrical maintenance service", 42, "MEDIUM", "CONFIRMED",
             ["NEW_RECIPIENT"],["First transaction to this vendor"], [], "legit"),
            (6, 20, 18000, "Online Training Platform", "edtech.courses@paytm", "UPI",
             "Annual subscription renewal", 45, "MEDIUM", "CONFIRMED",
             ["ELEVATED_AMOUNT"],["Amount higher than typical"], [], "legit"),
            (9, 15, 22000, "Krishna Transport Co", "krishna.transport@ybl", "NEFT",
             "Logistics payment bulk order", 51, "MEDIUM", "CONFIRMED",
             ["NEW_RECIPIENT","HIGH_AMOUNT_SPIKE"],["New transport vendor","Amount 2.8x your average"], [], "legit"),
            (12, 8, 5000, "Freelance Designer Payment", "freelancer.design@upi", "UPI",
             "Logo design work payment", 40, "MEDIUM", "CONFIRMED",
             ["NEW_RECIPIENT"],["First payment to this freelancer"], [], "legit"),
            (1, 11, 3200, "Maharashtra Electricity Board", "mahaelectricity@bescom", "UPI",
             "Monthly electricity bill Oct 2024", 8, "LOW", "CONFIRMED", [], [], [], "legit"),
            (2, 10, 45000, "Reliance Industries Ltd", "reliance.mumbai@hdfc", "NEFT",
             "Inventory purchase Q3 2024", 5, "LOW", "CONFIRMED", [], [], [], "legit"),
            (3, 14, 1800, "Zomato Business Account", "zomato.biz@icici", "UPI",
             "Staff lunch order October", 5, "LOW", "CONFIRMED", [], [], [], "legit"),
            (5, 9, 15000, "Tata Steel Distributors", "tatasteel.dist@hdfcbank", "NEFT",
             "Raw material purchase regular order", 5, "LOW", "CONFIRMED", [], [], [], "legit"),
            (7, 11, 2500, "Indian Oil Corporation", "iocl.petrol@axis", "UPI",
             "Fleet fuel expense Oct week 1", 3, "LOW", "CONFIRMED", [], [], [], "legit"),
            (8, 10, 8000, "Office Supplies Mart", "officemartpune@paytm", "UPI",
             "Stationery and office supplies", 8, "LOW", "CONFIRMED", [], [], [], "legit"),
            (15, 16, 120000, "HDFC Bank EMI", "hdfcbank.emi@hdfcbank", "NEFT",
             "Term loan EMI 24 Loan Account 4521891", 12, "LOW", "CONFIRMED",
             ["VERY_HIGH_AMOUNT"],["Above 1L within expected EMI range"], [], "legit"),
        ]

        print("  [Shield] Seeding 20 fraud protection scenarios...")
        for (days_ago, hour, amount, recipient, upi_id, method, desc,
             score, level, status, flagz, explz, kws, feedback) in scenarios:
            created = now - timedelta(days=days_ago)
            txn = FraudTransaction(
                org_id=tenant.id, user_id=user.id,
                amount=amount, recipient_name=recipient, recipient_id=upi_id,
                payment_method=method, description=desc,
                device_id="demo-device-apex-001", location="Pune, Maharashtra",
                transaction_hour=hour, risk_score=score, risk_level=level,
                risk_flags=json.dumps(flagz), risk_explanation=json.dumps(explz),
                scam_keywords_found=json.dumps(kws), vulnerable_user_mode=False,
                trusted_contact_alerted=(level == "HIGH"),
                trusted_contact_name="Anjali Gupta (Daughter)" if level == "HIGH" else None,
                status=status,
                resolved_at=created + timedelta(minutes=5) if status != "PENDING" else None,
                user_feedback=feedback, created_at=created,
            )
            db.session.add(txn)

        chat_samples = [
            ("Someone called from SBI and asked me to share OTP",
             "NEVER share your OTP - this is OTP Phishing. Hang up and call 1930.", True, "OTP Phishing"),
            ("Why was my transaction to Reliance flagged?",
             "Reliance transaction was LOW risk (5/100) - recognized vendor, auto-confirmed.", False, "System Explanation"),
            ("I got a message that I won a lucky draw prize",
             "This is a Prize Scam! Block the sender and report to cybercrime.gov.in.", True, "Prize/Lottery Scam"),
        ]
        import random as _r
        for query, response, is_scam, category in chat_samples:
            db.session.add(ScamReport(
                org_id=tenant.id, user_id=user.id, query=query, response=response,
                is_scam_detected=is_scam, scam_category=category,
                created_at=now - timedelta(days=_r.randint(1, 10)),
            ))

        db.session.commit()
        print("  [Shield] SmartShield data seeded successfully!")

if __name__ == "__main__":
    run()
    seed_smartshield(app)
