import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()
db_url = os.getenv("DATABASE_URL")
if db_url.startswith("mysql:"):
    db_url = db_url.replace("mysql:", "mysql+pymysql:", 1)
elif "mysql+aiomysql" in db_url:
    db_url = db_url.replace("mysql+aiomysql", "mysql+pymysql")

engine = create_engine(db_url)
with engine.connect() as conn:
    res = conn.execute(text("SELECT email, role, full_name FROM users WHERE role IN ('SUPER_ADMIN', 'ADMIN') AND status = 'ACTIVE'")).all()
    for row in res:
        print(f"Email: {row[0]} | Role: {row[1]} | Name: {row[2]}")
