import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import json

load_dotenv()
engine = create_engine(os.getenv('DATABASE_URL'))

with engine.connect() as conn:
    roles = conn.execute(text("SELECT name, permissions FROM roles")).fetchall()
    print("ROLES DATA:")
    for name, perms in roles:
        print(f"ROLE: {name}")
        print(f"RAW PERMS: {perms}")
        try:
            p_obj = json.loads(perms) if isinstance(perms, str) else perms
            print(f"PARSED: {json.dumps(p_obj, indent=2)}")
        except Exception as e:
            print(f"ERROR PARSING: {e}")
        print("-" * 30)
