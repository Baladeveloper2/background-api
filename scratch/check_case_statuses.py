import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()
engine = create_engine(os.getenv('DATABASE_URL'))

def run():
    with engine.connect() as conn:
        res = conn.execute(text("SELECT status, COUNT(*) FROM cases GROUP BY status"))
        print("--- Case Statuses ---")
        for row in res.fetchall():
            print(f"Status: {row[0]}, Count: {row[1]}")

        res = conn.execute(text("SELECT status, COUNT(*) FROM verification_checks GROUP BY status"))
        print("\n--- Check Statuses ---")
        for row in res.fetchall():
            print(f"Status: {row[0]}, Count: {row[1]}")

if __name__ == "__main__":
    run()
