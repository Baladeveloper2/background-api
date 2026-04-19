import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import json

load_dotenv()
engine = create_engine(os.getenv('DATABASE_URL'))

with engine.connect() as conn:
    roles = conn.execute(text("SELECT id, name, permissions FROM roles")).fetchall()
    print("ALL ROLES PERMISSIONS:")
    for r in roles:
        print(f"ID: {r[0]} | NAME: {r[1]}")
        p_raw = r[2]
        print(f"RAW: {p_raw}")
        try:
            p_obj = json.loads(p_raw) if isinstance(p_raw, str) else p_raw
            print(f"IS_OBJECT: {isinstance(p_obj, dict)}")
            if isinstance(p_obj, dict):
                for k, v in p_obj.items():
                    print(f"  {k}: {v} (TYPE: {type(v)})")
        except:
            print("FAILED TO PARSE")
        print("-" * 40)
