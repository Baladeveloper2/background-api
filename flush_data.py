import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("DATABASE_URL not found in .env")
    exit(1)

# Ensure syncing driver
if "mysql://" in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace("mysql://", "mysql+pymysql://")

engine = create_engine(DATABASE_URL)

tables_to_flush = [
    "verification_checks",
    "cases",
    "candidates",
    "batches",
    "customers",
    "partners",
    "audit_logs"
]

def flush_db():
    try:
        with engine.connect() as conn:
            print("Starting DB flush (All tables except users/roles/modules)...")
            # Disable FK checks to allow truncation of parent-child tables safely
            conn.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
            
            for table in tables_to_flush:
                print(f"Flushing table: {table}")
                try:
                    conn.execute(text(f"DELETE FROM {table}"))
                    print(f"Successfully flushed {table}")
                except Exception as e:
                    print(f"Error flushing {table}: {e}")
            
            # Re-enable FK checks
            conn.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
            conn.commit()
            print("\nDatabase flush complete. Applications/Cases/Clients data has been cleared.")
    except Exception as e:
        print(f"Critical error: {e}")

if __name__ == "__main__":
    flush_db()
