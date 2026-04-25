
from sqlalchemy import text
from app.database import sync_engine

def migrate():
    with sync_engine.begin() as conn:
        print("Migrating Candidate table (SYNC)...")
        columns = [
            ("pan_no", "VARCHAR(50)"),
            ("passport_no", "VARCHAR(50)"),
            ("nationality", "VARCHAR(100)"),
            ("identity_type", "VARCHAR(100)"),
            ("db_candidate_name", "VARCHAR(255)"),
            ("db_dob", "DATE"),
            ("database_scope", "VARCHAR(255)")
        ]
        
        for name, type in columns:
            try:
                conn.execute(text(f"ALTER TABLE candidates ADD COLUMN {name} {type}"))
                print(f"Added {name}")
            except Exception as e:
                if "Duplicate column name" in str(e) or "1060" in str(e):
                    print(f"Column {name} already exists")
                else:
                    print(f"Error adding {name}: {e}")
        
        print("Migration complete.")

if __name__ == "__main__":
    migrate()
