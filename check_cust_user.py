import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()
engine = create_engine(os.getenv('DATABASE_URL'))

with engine.connect() as conn:
    user = conn.execute(text("SELECT email, customer_id, role FROM users WHERE email='customer@bgvms.com'")).fetchone()
    if user:
        print(f"EMAIL: {user[0]}")
        print(f"CUSTOMER_ID: {user[1]}")
        print(f"ROLE: {user[2]}")
    else:
        print("User not found")
