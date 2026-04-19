import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import json

load_dotenv()
engine = create_engine(os.getenv('DATABASE_URL'))

with engine.connect() as conn:
    roles = conn.execute(text("SELECT id, name, permissions FROM roles")).fetchall()
    print("ROLES PERMISSIONS:")
    for r in roles:
        print(f"ID: {r[0]} | NAME: {r[1]}")
        p_raw = r[2]
        print(f"RAW: {p_raw}")
        print("-" * 20)
