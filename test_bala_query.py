
import sys
import os

sys.path.append(r'd:\project\backend')

from app.database import SYNC_URL
from app.models import Case, User, UserRole
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

engine = create_engine(SYNC_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
db = SessionLocal()

try:
    bala = db.query(User).filter(User.email == "bala@example.com").first()
    print(f"Bala ID: {bala.id}")
    print(f"Bala Role: {bala.role}")

    # Simulate the query in read_cases
    stmt = db.query(Case)
    if bala.role not in [UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.MANAGER]:
        print("Filtering by assigned_to...")
        stmt = stmt.filter(Case.assigned_to == bala.id)
    
    cases = stmt.all()
    print(f"Found {len(cases)} cases.")
    for c in cases:
        print(f"Case: {c.case_ref_no} | Assigned To: {c.assigned_to} | Status: {c.status}")

finally:
    db.close()
