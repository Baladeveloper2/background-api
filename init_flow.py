
import sys
import os

sys.path.append(r'd:\project\backend')

from app.database import SYNC_URL
from app.models import Case, Candidate, Customer, User, UserRole, VerificationCheck, CheckStatus, CaseStatus
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime

engine = create_engine(SYNC_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
db = SessionLocal()

try:
    # 1. Get Customer (TCS)
    customer = db.query(Customer).filter(Customer.name.like("%Tata Consultancy%")).first()
    if not customer:
        customer = db.query(Customer).first()
    
    # 2. Get Bala
    bala = db.query(User).filter(User.email == "bala@example.com").first()
    if not bala:
        print("Bala not found.")
        sys.exit(1)

    # 3. Create Candidate
    candidate = Candidate(
        name="John Verified",
        email="john.verified@example.com",
        phone="9876543210",
        address="123 Verification St, Bangalore"
    )
    db.add(candidate)
    db.flush()

    # 4. Create Case
    case_ref = f"FLOW-{datetime.now().strftime('%M%S')}"
    case = Case(
        case_ref_no=case_ref,
        customer_id=customer.id,
        candidate_id=candidate.id,
        status=CaseStatus.VERIFICATION,
        assigned_to=bala.id,
        received_date=datetime.now()
    )
    db.add(case)
    db.flush()

    # 5. Add Checks
    checks = ["Address", "Education", "Employment"]
    for c_type in checks:
        check = VerificationCheck(
            case_id=case.id,
            check_type=c_type,
            status=CheckStatus.INTERIM,
            data={}
        )
        db.add(check)

    db.commit()
    print(f"Flow initialized: Case {case_ref} assigned to Bala.")

finally:
    db.close()
