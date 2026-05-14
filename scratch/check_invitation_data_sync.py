
import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
# Ensure it uses pymysql for sync
if DATABASE_URL and "mysql" in DATABASE_URL and "+pymysql" not in DATABASE_URL:
    if "://" in DATABASE_URL:
        proto, rest = DATABASE_URL.split("://")
        if "+" in proto:
            DATABASE_URL = "mysql+pymysql://" + rest
        else:
            DATABASE_URL = "mysql+pymysql://" + rest

engine = create_engine(DATABASE_URL)

def check():
    with engine.connect() as session:
        res = session.execute(text("SELECT id, status, received_date FROM cases WHERE status = 'DOCUMENTS_SUBMITTED' LIMIT 5"))
        cases = res.fetchall()
        print("Cases with DOCUMENTS_SUBMITTED:")
        for c in cases:
            print(f"ID: {c[0]}, Status: {c[1]}, Received Date: {c[2]}")
            
        res = session.execute(text("SELECT id, status, received_date FROM cases WHERE status = 'LINK_SHARED' LIMIT 5"))
        cases = res.fetchall()
        print("\nCases with LINK_SHARED:")
        for c in cases:
            print(f"ID: {c[0]}, Status: {c[1]}, Received Date: {c[2]}")

if __name__ == "__main__":
    check()
