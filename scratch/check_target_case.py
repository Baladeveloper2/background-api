import os
import sys
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()
db_url = os.getenv("DATABASE_URL")
if not db_url:
    print("No DATABASE_URL found!")
    sys.exit(1)

if db_url.startswith("mysql:"):
    db_url = db_url.replace("mysql:", "mysql+pymysql:", 1)
elif "mysql+aiomysql" in db_url:
    db_url = db_url.replace("mysql+aiomysql", "mysql+pymysql")

engine = create_engine(db_url)
case_id = "297b7056-e526-4f8c-a686-1f71ae959f5b"

with engine.connect() as conn:
    print("--- CASE DETAILS ---")
    case_res = conn.execute(text("SELECT id, status, qc_revoke_count, verifier_revoke_count, completed_date, final_result FROM cases WHERE id = :cid"), {"cid": case_id}).first()
    if not case_res:
        print("Case not found!")
    else:
        print(f"ID: {case_res[0]}")
        print(f"Status: {case_res[1]}")
        print(f"QC Revoke Count: {case_res[2]}")
        print(f"Verifier Revoke Count: {case_res[3]}")
        print(f"Completed Date: {case_res[4]}")
        print(f"Final Result: {case_res[5]}")

    print("\n--- CHECKS DETAILS ---")
    checks_res = conn.execute(text("SELECT id, check_type, status, final_result FROM verification_checks WHERE case_id = :cid"), {"cid": case_id}).all()
    for row in checks_res:
        print(f"Check ID: {row[0]} | Type: {row[1]} | Status: {row[2]} | Final Result: {row[3]}")
