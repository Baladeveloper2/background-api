
import sys
import os

sys.path.append(r'd:\project\backend')

from app.database import SYNC_URL
from app.models import Case, User, UserRole
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

engine = create_engine(SYNC_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
db = SessionLocal()

try:
    # Find Bala 
    bala = db.query(User).filter(User.email == "bala@example.com").first()
    if not bala:
        print("Bala not found.")
        sys.exit(1)

    # Find a pending case
    case = db.query(Case).filter(Case.status == "PENDING").first()
    if not case:
        print("No pending cases found.")
    else:
        print(f"Assigning Case {case.case_ref_no} to Bala...")
        case.assigned_to = bala.id
        case.status = "VERIFICATION"
        db.commit()
        print("Assignment successful.")

finally:
    db.close()
