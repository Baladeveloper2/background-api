
import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL and "mysql" in DATABASE_URL and "+pymysql" not in DATABASE_URL:
    if "://" in DATABASE_URL:
        proto, rest = DATABASE_URL.split("://")
        DATABASE_URL = "mysql+pymysql://" + rest

engine = create_engine(DATABASE_URL)

def check_logs():
    with engine.connect() as session:
        case_id = "454f542d-b2ad-496e-9f1f-e6264db9de5d" # A DOCS_SUBMITTED case
        res = session.execute(text("SELECT action, new_status, created_at FROM verification_logs WHERE case_id = :cid"), {"cid": case_id})
        logs = res.fetchall()
        print(f"Logs for Case {case_id}:")
        for l in logs:
            print(f"Action: {l[0]}, Status: {l[1]}, Time: {l[2]}")

if __name__ == "__main__":
    check_logs()
