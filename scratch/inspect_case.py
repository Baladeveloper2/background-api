import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

RAW_URL = os.getenv("DATABASE_URL")
if "://" in RAW_URL:
    base = RAW_URL.split("://")[1]
    SYNC_URL = f"mysql+pymysql://{base}"
else:
    SYNC_URL = RAW_URL

engine = create_engine(SYNC_URL)
case_id = "b438ff7b-8510-470d-b62e-42987e099b05"

with engine.connect() as conn:
    # 1. Print Case details
    res = conn.execute(text("SELECT id, case_ref_no, status, final_result FROM cases WHERE id = :case_id"), {"case_id": case_id}).fetchone()
    print("CASE:", res)
    
    # 2. Print Checks details
    checks = conn.execute(text("SELECT id, check_type, status, final_result, finalized_by FROM verification_checks WHERE case_id = :case_id"), {"case_id": case_id}).fetchall()
    print("\nCHECKS:")
    for chk in checks:
        print(chk)
