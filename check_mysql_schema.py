from app.database import engine
from sqlalchemy import text

with engine.connect() as conn:
    result = conn.execute(text("DESCRIBE customers"))
    rows = result.fetchall()
    with open("schema_output.txt", "w") as f:
        for row in rows:
            f.write(f"Column: {row[0]}, Type: {row[1]}, Null: {row[2]}, Key: {row[3]}, Default: {row[4]}, Extra: {row[5]}\n")
