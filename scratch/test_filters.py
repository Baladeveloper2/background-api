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
client_name = "Apex Covantage India Private Limited"
start_date = datetime(2026, 5, 1)
end_date = datetime(2026, 5, 15, 23, 59, 59)

with engine.connect() as conn:
    # Get customer id
    cust = conn.execute(text("SELECT id FROM customers WHERE name = :name"), {"name": client_name}).first()
    if not cust:
        print("Customer not found!")
    else:
        cust_id = cust[0]
        print(f"Customer ID: {cust_id}")
        
        # Count cases
        cnt = conn.execute(text("SELECT count(*) FROM cases WHERE customer_id = :cid"), {"cid": cust_id}).scalar()
        print(f"Total cases ever for customer: {cnt}")
        
        # Count cases in date range
        cnt_range = conn.execute(
            text("SELECT count(*), status FROM cases WHERE customer_id = :cid AND received_date >= :s AND received_date <= :e GROUP BY status"),
            {"cid": cust_id, "s": start_date, "e": end_date}
        ).all()
        print("Cases in date range May 1 to May 15:")
        for row in cnt_range:
            print(f"Status: {row[1]} | Count: {row[0]}")
