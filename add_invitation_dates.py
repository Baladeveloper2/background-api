
import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL and "mysql" in DATABASE_URL and "+pymysql" not in DATABASE_URL:
    if "://" in DATABASE_URL:
        proto, rest = DATABASE_URL.split("://")
        DATABASE_URL = "mysql+pymysql://" + rest

engine = create_engine(DATABASE_URL)

def migrate():
    with engine.connect() as conn:
        print("Adding invitation lifecycle columns to cases table...")
        try:
            conn.execute(text("ALTER TABLE cases ADD COLUMN link_shared_at DATETIME"))
            conn.execute(text("ALTER TABLE cases ADD COLUMN submitted_at DATETIME"))
            print("Successfully added link_shared_at and submitted_at columns.")
        except Exception as e:
            print(f"Error adding columns (they might already exist): {e}")
        
        conn.commit()

if __name__ == "__main__":
    migrate()
