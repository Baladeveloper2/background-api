
import sys
import os

sys.path.append(r'd:\project\backend')

from app.database import SYNC_URL
from app.models import Case, Candidate, VerificationCheck
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

engine = create_engine(SYNC_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
db = SessionLocal()

try:
    # 1. Find Case
    case_ref = "FLOW-2253"
    case = db.query(Case).filter(Case.case_ref_no == case_ref).first()
    
    if not case:
        print(f"Case {case_ref} not found.")
        sys.exit(1)
        
    candidate = case.candidate
    print(f"Updating data for Candidate: {candidate.name}")

    # 2. Update Candidate Address Details
    candidate.address_details = {
        "addresses": [
            {
                "line1": "123 Verification St",
                "line2": "HSR Layout",
                "city": "Bangalore",
                "state": "Karnataka",
                "pincode": "560102",
                "period_from": "2020-01-01",
                "period_to": "Present"
            }
        ],
        "educations": [
            {
                "university": "Visvesvaraya Technological University",
                "institution": "PESIT Bangalore",
                "degree_name": "B.E. Computer Science",
                "reg_no": "1PI16CS001",
                "year_of_passing": "2020"
            }
        ],
        "employments": [
            {
                "employer": "Tata Consultancy Services (TCS)",
                "designation": "Systems Engineer",
                "employee_code": "TCS123456",
                "date_of_joining": "2021-01-15",
                "date_of_leaving": "Present",
                "salary": "8,50,000 PA"
            }
        ],
        "criminals": [],
        "identities": [
            {
                "type": "Aadhar Card",
                "number": "XXXX-XXXX-1234"
            }
        ]
    }

    db.add(candidate)
    db.commit()
    print(f"Successfully updated basic details for {candidate.name} in case {case_ref}.")

finally:
    db.close()
