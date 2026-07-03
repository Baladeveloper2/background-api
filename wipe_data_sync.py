import os
from sqlalchemy import create_engine
from sqlalchemy import text
from dotenv import load_dotenv

load_dotenv()

engine = create_engine(os.getenv('DATABASE_URL'))

def run():
    with engine.begin() as conn:
        print("Wiping data...")
        conn.execute(text("SET FOREIGN_KEY_CHECKS=0;"))
        tables = [
            "client_documents",
            "audit_logs",
            "notifications",
            "insufficiencies",
            "verification_checks",
            "case_activity",
            "cases",
            "candidates",
            "branches",
            "customers",
            "zones"
        ]
        for table in tables:
            try:
                conn.execute(text(f"DELETE FROM {table}"))
                print(f"Cleared {table}")
            except Exception as e:
                print(f"Skipping {table}: {e}")
        
        # Keep super admins
        conn.execute(text("DELETE FROM users WHERE role != 'SUPER_ADMIN' AND role_id IS NULL"))
        
        conn.execute(text("SET FOREIGN_KEY_CHECKS=1;"))
        print("Done wiping!")

if __name__ == "__main__":
    run()
