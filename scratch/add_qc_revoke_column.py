import os
import sys
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
    print("Checking if column qc_revoke_count exists on cases table...")
    # Check if the column exists
    columns_res = conn.execute(text("DESCRIBE cases")).all()
    col_names = [col[0] for col in columns_res]
    
    if "qc_revoke_count" in col_names:
        print("Column qc_revoke_count already exists. No migration needed.")
    else:
        print("Adding column qc_revoke_count to cases table...")
        try:
            conn.execute(text("ALTER TABLE cases ADD COLUMN qc_revoke_count INT DEFAULT 0 AFTER verifier_revoke_count"))
            conn.commit()
            print("Successfully added qc_revoke_count column!")
        except Exception as e:
            print(f"Error adding column: {e}")
