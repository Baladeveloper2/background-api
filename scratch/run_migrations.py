
import sys
import os

# Add the current directory to sys.path
sys.path.append(os.getcwd())

from app.database import sync_engine
from sqlalchemy import text

def run_migrations():
    with sync_engine.connect() as conn:
        print("Migrating 'customers' table...")
        try:
            # Check if column exists first to avoid error if already added partially
            res = conn.execute(text("SHOW COLUMNS FROM customers LIKE 'short_code'"))
            if not res.fetchone():
                conn.execute(text("ALTER TABLE customers ADD COLUMN short_code VARCHAR(50) AFTER name"))
                conn.execute(text("CREATE UNIQUE INDEX ix_customers_short_code ON customers (short_code)"))
                print("Successfully added 'short_code' to 'customers'.")
            else:
                print("'short_code' already exists in 'customers'.")
        except Exception as e:
            print(f"Error migrating 'customers': {e}")

        print("Migrating 'batches' table...")
        try:
            res = conn.execute(text("SHOW COLUMNS FROM batches LIKE 'cl_ref_no'"))
            if not res.fetchone():
                conn.execute(text("ALTER TABLE batches ADD COLUMN cl_ref_no VARCHAR(50) AFTER batch_no"))
                conn.execute(text("CREATE INDEX ix_batches_cl_ref_no ON batches (cl_ref_no)"))
                print("Successfully added 'cl_ref_no' to 'batches'.")
            else:
                print("'cl_ref_no' already exists in 'batches'.")
        except Exception as e:
            print(f"Error migrating 'batches': {e}")
        
        conn.commit()

if __name__ == "__main__":
    run_migrations()
