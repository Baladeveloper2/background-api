import sys
sys.path.append(r'd:\project\backend')

from app.database import SYNC_URL
from sqlalchemy import create_engine, text

engine = create_engine(SYNC_URL)

with engine.connect() as conn:
    res = conn.execute(text("SELECT id, email, role, full_name FROM users"))
    users = res.fetchall()
    for u in users:
        print(f"ID: {u[0]}, Email: {u[1]}, Role: {u[2]}, Name: {u[3]}")
