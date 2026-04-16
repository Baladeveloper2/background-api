from sqlalchemy import text
from app.database import engine

def check_schema():
    with engine.connect() as conn:
        print(f"Connecting to: {engine.url}")
        res = conn.execute(text("DESCRIBE cases"))
        rows = res.fetchall()
        print("Columns in 'cases' table:")
        for row in rows:
            print(f" - {row[0]}: {row[1]}")

if __name__ == "__main__":
    check_schema()
