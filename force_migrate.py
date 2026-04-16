from sqlalchemy import text
from app.database import engine

def force_migrate():
    with engine.connect() as conn:
        print("Forcing migration...")
        try:
            conn.execute(text("ALTER TABLE cases ADD COLUMN qa_id INT NULL"))
            print("qa_id command sent.")
        except Exception as e:
            print(f"qa_id error: {e}")
            
        try:
            conn.execute(text("ALTER TABLE cases ADD COLUMN qc_id INT NULL"))
            print("qc_id command sent.")
        except Exception as e:
            print(f"qc_id error: {e}")
            
        conn.commit()
        print("Committed.")

if __name__ == "__main__":
    force_migrate()
