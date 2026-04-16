
import sys
import os

sys.path.append(r'd:\project\backend')

from app.database import SYNC_URL
from app.models import User, Role
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

engine = create_engine(SYNC_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
db = SessionLocal()

try:
    print("Listing all users:")
    users = db.query(User).all()
    for u in users:
        role_name = db.query(Role).filter(Role.id == u.role_id).first().name if u.role_id else u.role
        print(f"User: {u.full_name} | Email: {u.email} | Role: {role_name}")
finally:
    db.close()
