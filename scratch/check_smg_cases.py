import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from datetime import datetime

load_dotenv()
db_url = os.getenv("DATABASE_URL")
if db_url.startswith("mysql:"):
    db_url = db_url.replace("mysql:", "mysql+pymysql:", 1)
elif "mysql+aiomysql" in db_url:
    db_url = db_url.replace("mysql+aiomysql", "mysql+pymysql")

engine = create_engine(db_url)
client_name = "SMG Enterprises"
start_date = datetime(2026, 5, 1)
end_date = datetime(2026, 5, 10, 23, 59, 59)

with engine.connect() as conn:
    # 1. Get customer
    cust = conn.execute(text("SELECT id, name FROM customers WHERE name = :name"), {"name": client_name}).first()
    if not cust:
        print("Customer SMG Enterprises not found!")
    else:
        cust_id, name = cust
        print(f"Customer: {name} | ID: {cust_id}")
        
        # Count all cases
        cnt = conn.execute(text("SELECT count(*) FROM cases WHERE customer_id = :cid"), {"cid": cust_id}).scalar()
        print(f"Total cases ever: {cnt}")
        
        # List all cases
        cases = conn.execute(text("SELECT id, case_ref_no, status, received_date FROM cases WHERE customer_id = :cid"), {"cid": cust_id}).all()
        for c in cases:
            print(f"Case Ref: {c[1]} | Status: {c[2]} | Received Date: {c[3]}")
