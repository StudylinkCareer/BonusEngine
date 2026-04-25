"""
migrate.py
==========
Safe migration script — adds missing columns to existing tables.
Run from backend/ folder:
    python migrate.py

Safe to re-run — checks if columns exist before adding them.
"""

import sys, os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database import engine
from sqlalchemy import text

def column_exists(conn, table, column):
    result = conn.execute(text(
        f"SELECT column_name FROM information_schema.columns "
        f"WHERE table_name='{table}' AND column_name='{column}'"
    ))
    return result.fetchone() is not None

def migrate():
    with engine.connect() as conn:
        print("Running migrations...\n")

        # --- ref_staff_names: add 'scheme' column ---
        if not column_exists(conn, "ref_staff_names", "scheme"):
            conn.execute(text(
                "ALTER TABLE ref_staff_names ADD COLUMN scheme VARCHAR(30)"
            ))
            conn.commit()
            print("✅ Added 'scheme' column to ref_staff_names")
        else:
            print("⏭  ref_staff_names.scheme already exists")

        # --- ref_staff_names: add 'start_date' column ---
        if not column_exists(conn, "ref_staff_names", "start_date"):
            conn.execute(text(
                "ALTER TABLE ref_staff_names ADD COLUMN start_date DATE"
            ))
            conn.commit()
            print("✅ Added 'start_date' column to ref_staff_names")
        else:
            print("⏭  ref_staff_names.start_date already exists")

        # --- ref_staff_names: add 'end_date' column ---
        if not column_exists(conn, "ref_staff_names", "end_date"):
            conn.execute(text(
                "ALTER TABLE ref_staff_names ADD COLUMN end_date DATE"
            ))
            conn.commit()
            print("✅ Added 'end_date' column to ref_staff_names")
        else:
            print("⏭  ref_staff_names.end_date already exists")

        # --- advance_payments: check all columns exist ---
        ap_columns = {
            "contract_id":        "VARCHAR(20)",
            "student_name":       "VARCHAR(200)",
            "period_month":       "INTEGER",
            "period_year":        "INTEGER",
            "advance_paid":       "INTEGER DEFAULT 0",
            "status_at_payment":  "VARCHAR(100)",
            "full_bonus_at_tier": "INTEGER DEFAULT 0",
            "payment_type":       "VARCHAR(20) DEFAULT 'Advance'",
            "is_settled":         "BOOLEAN DEFAULT FALSE",
            "settled_at":         "TIMESTAMP",
            "recorded_at":        "TIMESTAMP",
        }
        for col, col_type in ap_columns.items():
            if not column_exists(conn, "advance_payments", col):
                conn.execute(text(
                    f"ALTER TABLE advance_payments ADD COLUMN {col} {col_type}"
                ))
                conn.commit()
                print(f"✅ Added '{col}' column to advance_payments")
            else:
                print(f"⏭  advance_payments.{col} already exists")

        # --- Create ref_service_fee_rates if not exists ---
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS ref_service_fee_rates (
                id SERIAL PRIMARY KEY,
                fee_type VARCHAR(50) UNIQUE NOT NULL,
                rate_pct FLOAT DEFAULT 0.0,
                flat_amount INTEGER DEFAULT 0,
                note VARCHAR(200),
                is_active BOOLEAN DEFAULT TRUE
            )
        """))
        conn.commit()
        print("✅ ref_service_fee_rates table ensured")

        # --- ref_status_rules: add missing columns ---
        sr_columns = {
            "counts_as_enrolled":     "BOOLEAN DEFAULT FALSE",
            "is_carry_over":          "BOOLEAN DEFAULT FALSE",
            "is_current_enrolled":    "BOOLEAN DEFAULT FALSE",
            "is_zero_bonus":          "BOOLEAN DEFAULT FALSE",
            "fees_paid_non_enrolled": "BOOLEAN DEFAULT FALSE",
            "requires_visa":          "BOOLEAN DEFAULT FALSE",
            "requires_enrol":         "BOOLEAN DEFAULT FALSE",
            "dedup_rank":             "INTEGER DEFAULT 0",
            "conditions":             "TEXT",
            "triggers":               "TEXT",
            "note":                   "VARCHAR(300)",
        }
        for col, col_type in sr_columns.items():
            if not column_exists(conn, "ref_status_rules", col):
                conn.execute(text(
                    f"ALTER TABLE ref_status_rules ADD COLUMN {col} {col_type}"
                ))
                conn.commit()
                print(f"✅ Added '{col}' column to ref_status_rules")
            else:
                print(f"⏭  ref_status_rules.{col} already exists")

        print("\n✅ All migrations complete!")

if __name__ == "__main__":
    migrate()
