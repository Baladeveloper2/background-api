import os
import sys
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Load backend dotenv
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

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
    print("Checking if columns exist on insufficiencies table...")
    columns_res = conn.execute(text("DESCRIBE insufficiencies")).all()
    col_names = [col[0] for col in columns_res]
    print("Current columns:", col_names)
    
    # 1. notification_count
    if "notification_count" not in col_names:
        print("Adding notification_count column...")
        conn.execute(text("ALTER TABLE insufficiencies ADD COLUMN notification_count INT DEFAULT 0"))
        conn.commit()
    
    # 2. last_notified_at
    if "last_notified_at" not in col_names:
        print("Adding last_notified_at column...")
        conn.execute(text("ALTER TABLE insufficiencies ADD COLUMN last_notified_at DATETIME"))
        conn.commit()

    # 3. response_at
    if "response_at" not in col_names:
        print("Adding response_at column...")
        conn.execute(text("ALTER TABLE insufficiencies ADD COLUMN response_at DATETIME"))
        conn.commit()

    # 4. timeline
    if "timeline" not in col_names:
        print("Adding timeline column...")
        conn.execute(text("ALTER TABLE insufficiencies ADD COLUMN timeline MEDIUMTEXT"))
        conn.commit()

    print("Checking final columns on insufficiencies table...")
    columns_res_final = conn.execute(text("DESCRIBE insufficiencies")).all()
    col_names_final = [col[0] for col in columns_res_final]
    print("Final columns:", col_names_final)
