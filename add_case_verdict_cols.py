from sqlalchemy import text
from app.database import sync_engine
import sys

print("Starting database migration to add final case verdict columns...")
try:
    with sync_engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE cases ADD COLUMN final_result VARCHAR(50) NULL"))
            print("[SUCCESS] Column 'final_result' added successfully to 'cases' table.")
        except Exception as e:
            if "Duplicate column name" in str(e) or "1060" in str(e):
                print("[SKIP] Column 'final_result' already exists.")
            else:
                print(f"[ERROR] Failed to add final_result: {e}")

        try:
            conn.execute(text("ALTER TABLE cases ADD COLUMN qc_remarks TEXT NULL"))
            print("[SUCCESS] Column 'qc_remarks' added successfully to 'cases' table.")
        except Exception as e:
            if "Duplicate column name" in str(e) or "1060" in str(e):
                print("[SKIP] Column 'qc_remarks' already exists.")
            else:
                print(f"[ERROR] Failed to add qc_remarks: {e}")
        
        conn.commit()
        print("[DONE] Migration transaction committed successfully.")
except Exception as top_level_error:
    print(f"FATAL ERROR: {top_level_error}")
    sys.exit(1)
