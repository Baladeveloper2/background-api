import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    exit(1)
if DATABASE_URL.startswith("mysql:"):
    DATABASE_URL = DATABASE_URL.replace("mysql:", "mysql+pymysql:", 1)

engine = create_engine(DATABASE_URL)

with engine.connect() as connection:
    try:
        connection.execute(text("SELECT case_rate FROM batches LIMIT 1"))
        print("case_rate exists")
    except Exception as e:
        print(f"case_rate missing: {e}")
        print("Adding case_rate...")
        connection.execute(text("ALTER TABLE batches ADD COLUMN case_rate FLOAT DEFAULT 0.0"))
        connection.commit()
        print("Success")
