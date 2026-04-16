import sys
from sqlalchemy import text
from app.database import engine

def migrate():
    print("--- Database Migration Tool ---")
    try:
        with engine.connect() as conn:
            print("Connected to database.")
            
            # Check existing columns
            res = conn.execute(text("DESCRIBE cases"))
            columns = [row[0] for row in res.fetchall()]
            print(f"Current columns: {columns}")
            
            if 'qa_id' not in columns:
                print("Adding qa_id...")
                conn.execute(text("ALTER TABLE cases ADD COLUMN qa_id INT NULL"))
                print("✓ qa_id added.")
            else:
                print("! qa_id already exists.")
                
            if 'qc_id' not in columns:
                print("Adding qc_id...")
                conn.execute(text("ALTER TABLE cases ADD COLUMN qc_id INT NULL"))
                print("✓ qc_id added.")
            else:
                print("! qc_id already exists.")
            
            conn.commit()
            print("Migration committed successfully.")
            
    except Exception as e:
        print(f"FATAL ERROR during migration: {e}")
        sys.exit(1)

if __name__ == "__main__":
    migrate()
