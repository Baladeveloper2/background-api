import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "mysql+pymysql://root:password@localhost/bgv_db")
if "mysql" in DATABASE_URL and "+pymysql" not in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace("mysql://", "mysql+pymysql://")

engine = create_engine(DATABASE_URL)

def migrate():
    with engine.connect() as conn:
        print("Adding branding columns to customers table...")
        try:
            conn.execute(text("ALTER TABLE customers ADD COLUMN brand_primary_color VARCHAR(20) DEFAULT '#7c3aed'"))
            conn.execute(text("ALTER TABLE customers ADD COLUMN brand_secondary_color VARCHAR(20) DEFAULT '#f5f3ff'"))
            conn.execute(text("ALTER TABLE customers ADD COLUMN logo_url VARCHAR(512)"))
            conn.execute(text("ALTER TABLE customers ADD COLUMN custom_domain VARCHAR(255)"))
            print("Successfully added branding columns.")
        except Exception as e:
            print(f"Error adding branding columns (they might already exist): {e}")

        print("Adding risk columns to cases table...")
        try:
            conn.execute(text("ALTER TABLE cases ADD COLUMN risk_score INTEGER DEFAULT 0"))
            conn.execute(text("ALTER TABLE cases ADD COLUMN risk_factors JSON"))
            conn.execute(text("ALTER TABLE cases ADD COLUMN last_risk_assessment DATETIME"))
            print("Successfully added risk columns.")
        except Exception as e:
            print(f"Error adding risk columns (they might already exist): {e}")
        
        conn.commit()

if __name__ == "__main__":
    migrate()
