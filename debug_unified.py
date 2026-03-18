from app.database import engine, SessionLocal
from app import models
from sqlalchemy import text
import traceback

with engine.connect() as conn:
    print("--- RAW SQL DESCRIBE ---")
    res = conn.execute(text("DESCRIBE customers"))
    for row in res:
        print(row)

print("\n--- SQLALCHEMY QUERY ---")
db = SessionLocal()
try:
    count = db.query(models.Customer).count()
    print(f"Customer Count: {count}")
except Exception as e:
    print(f"SQLAlchemy failed: {e}")
    # Print the compiled SQL
    from sqlalchemy.dialects import mysql
    q = db.query(models.Customer)
    print(f"Generated SQL: {q.statement.compile(dialect=mysql.dialect())}")
finally:
    db.close()
