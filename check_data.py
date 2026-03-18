from app.database import engine
from sqlalchemy import text

with engine.connect() as conn:
    with open("db_inspect.txt", "w") as f:
        f.write("Columns in customers:\n")
        res = conn.execute(text("DESCRIBE customers"))
        for row in res:
            f.write(str(row) + "\n")
        
        f.write("\nData in customers (limit 5):\n")
        try:
            res = conn.execute(text("SELECT id, name, active_status FROM customers LIMIT 5"))
            rows = res.fetchall()
            for row in rows:
                f.write(str(row) + "\n")
        except Exception as e:
            f.write(f"Error querying data: {e}\n")
