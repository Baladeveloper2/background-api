import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()
engine = create_engine(os.getenv('DATABASE_URL'))

def run():
    with engine.connect() as conn:
        print("Starting user role consolidation in database...")
        
        # Update QA, QC, USER to VERIFIER
        res1 = conn.execute(text("UPDATE users SET role = 'VERIFIER' WHERE role IN ('QA', 'QC', 'USER')"))
        print(f"Updated {res1.rowcount} users with QA/QC/USER to VERIFIER.")
        
        # Update ADMIN to SUPER_ADMIN
        res2 = conn.execute(text("UPDATE users SET role = 'SUPER_ADMIN' WHERE role = 'ADMIN'"))
        print(f"Updated {res2.rowcount} users with ADMIN to SUPER_ADMIN.")
        
        conn.commit()
        print("Role consolidation completed.")

if __name__ == "__main__":
    run()
