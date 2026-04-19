import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import json

load_dotenv()
engine = create_engine(os.getenv('DATABASE_URL'))

with engine.connect() as conn:
    roles = conn.execute(text("SELECT id, name, permissions FROM roles")).fetchall()
    with open("roles_dump.txt", "w", encoding="utf-8") as f:
        f.write("ALL ROLES PERMISSIONS:\n")
        for r in roles:
            f.write(f"ID: {r[0]} | NAME: {r[1]}\n")
            p_raw = r[2]
            f.write(f"RAW: {p_raw}\n")
            try:
                p_obj = json.loads(p_raw) if isinstance(p_raw, str) else p_raw
                if isinstance(p_obj, dict):
                    for k, v in p_obj.items():
                        f.write(f"  {k}: {v} (TYPE: {type(v)})\n")
            except:
                f.write("FAILED TO PARSE\n")
            f.write("-" * 40 + "\n")
