import os
import sys
import json
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()
db_url = os.getenv("DATABASE_URL")
if not db_url:
    print("No DATABASE_URL found!")
    sys.exit(1)

if db_url.startswith("mysql:"):
    db_url = db_url.replace("mysql:", "mysql+pymysql:", 1)
elif "mysql+aiomysql" in db_url:
    db_url = db_url.replace("mysql+aiomysql", "mysql+pymysql")

engine = create_engine(db_url)

with engine.connect() as conn:
    print("\n--- ALL UNIQUE CHECK TYPES & SAMPLE DATA ---")
    checks_res = conn.execute(text("SELECT check_type, data, status FROM verification_checks LIMIT 50")).all()
    for row in checks_res:
        t = row[0]
        data = row[1]
        status = row[2]
        
        # If it is a string representation of json, let's load it
        parsed_data = None
        if data:
            if isinstance(data, str):
                try:
                    parsed_data = json.loads(data)
                except:
                    parsed_data = data
            else:
                parsed_data = data
                
        print(f"Type: {t} | Status: {status}")
        print(f"Data: {json.dumps(parsed_data, indent=2) if isinstance(parsed_data, (dict, list)) else parsed_data}\n")
