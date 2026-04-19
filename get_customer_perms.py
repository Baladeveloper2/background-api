import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import json

load_dotenv()
engine = create_engine(os.getenv('DATABASE_URL'))

with engine.connect() as conn:
    role = conn.execute(text("SELECT name, permissions FROM roles WHERE name='Customer'")).fetchone()
    if role:
        print(f"ROLE: {role[0]}")
        print(f"PERMS: {role[1]}")
    else:
        print("Customer role not found")
