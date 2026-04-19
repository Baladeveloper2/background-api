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
        print(f"PERMS TYPE: {type(role[1])}")
        print(f"PERMS REPR: {repr(role[1])}")
        if isinstance(role[1], str):
            try:
                p = json.loads(role[1])
                print(f"PARSED KEYS: {list(p.keys())}")
                for k, v in p.items():
                    print(f"  {k}: {repr(v)}")
            except:
                print("Failed to parse JSON")
    else:
        print("Customer role not found")
