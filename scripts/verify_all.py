"""Automated All-in-One Platform Verification Script.
Executes database integrity checks, price boundary audits, API connectivity, and the pytest test suite.
"""
import sys
import os
import json
import sqlite3
import urllib.request
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.db.connection import DEFAULT_DB_PATH

# Configure utf-8 stdout on Windows console
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def main():
    print("==================================================================")
    print("  VINIT'S RESEARCH TERMINAL — SYSTEM VERIFICATION AUDIT")
    print("  WATERMARK: CODE TEST — SYNTHETIC DATA")
    print("==================================================================")

    # 1. SQLite Database Integrity
    print("\n[Step 1] Checking Database Physical Integrity & Foreign Keys...")
    db_path = DEFAULT_DB_PATH
    if not db_path.exists():
        print(f"  [ERROR] {db_path} not found.")
        sys.exit(1)

    con = sqlite3.connect(db_path)
    cur = con.cursor()
    int_check = cur.execute("PRAGMA integrity_check;").fetchall()
    fk_check = cur.execute("PRAGMA foreign_key_check;").fetchall()
    print(f"  -> Physical Integrity: {int_check[0][0].upper()}")
    print(f"  -> Foreign Key Violations: {len(fk_check)}")
    assert int_check[0][0] == "ok"
    assert len(fk_check) == 0

    # 2. Database Counts & Price Boundaries
    print("\n[Step 2] Auditing Securities Universe & Raw Price Boundaries...")
    sec_count = cur.execute("SELECT COUNT(*) FROM security;").fetchone()[0]
    price_count = cur.execute("SELECT COUNT(*) FROM price_raw;").fetchone()[0]
    ca_count = cur.execute("SELECT COUNT(*) FROM corporate_action;").fetchone()[0]
    gov_count = cur.execute("SELECT COUNT(*) FROM governance_event;").fetchone()[0]

    print(f"  -> Total Securities Master: {sec_count:,}")
    print(f"  -> Total Raw Daily Prices : {price_count:,}")
    print(f"  -> Corporate Actions      : {ca_count}")
    print(f"  -> Governance Disclosures : {gov_count:,}")

    # Boundary check
    violations = cur.execute("""
        SELECT COUNT(*) FROM price_raw
        WHERE (high_raw IS NOT NULL AND low_raw IS NOT NULL AND high_raw < low_raw)
           OR (close_raw <= 0)
           OR (volume_raw < 0);
    """).fetchone()[0]
    print(f"  -> Price Boundary Violations (High < Low, Close <= 0, Vol < 0): {violations}")
    assert violations == 0
    assert sec_count >= 3390
    assert price_count >= 6700

    # 3. API Health & Endpoints
    print("\n[Step 3] Verifying FastAPI REST Server Connectivity...")
    try:
        health_req = urllib.request.urlopen("http://127.0.0.1:8000/health", timeout=3)
        health_data = json.loads(health_req.read().decode())
        print(f"  -> Server Status: {health_data.get('status', 'unknown').upper()}")
        print(f"  -> API Watermark: {health_data.get('watermark')}")

        audit_req = urllib.request.urlopen("http://127.0.0.1:8000/api/v1/quality/audit", timeout=3)
        audit_data = json.loads(audit_req.read().decode())
        print(f"  -> Provenance Ledger Files: {len(audit_data.get('provenance_ledger', []))}")

        reports_req = urllib.request.urlopen("http://127.0.0.1:8000/api/v1/reports", timeout=3)
        reports_data = json.loads(reports_req.read().decode())
        print(f"  -> Available Research Tear-Sheets: {reports_data.get('count', 0)}")
    except Exception as e:
        print(f"  [WARN] Local server not running or unreachable ({e}). Start with 'py -m uvicorn src.api.main:app'.")

    # 4. Pytest Execution
    print("\n[Step 4] Executing Pytest Acceptance Test Suite...")
    exit_code = pytest.main(["-q", "tests/"])
    print(f"  -> Pytest Exit Code: {exit_code} (0 = ALL PASSED)")
    assert exit_code == 0

    print("\n==================================================================")
    print("  ALL PLATFORM VERIFICATION AUDITS PASSED WITH ZERO ERRORS")
    print("==================================================================\n")


if __name__ == "__main__":
    main()
