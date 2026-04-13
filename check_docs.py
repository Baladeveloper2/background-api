import os
import sys
# Add project root to path
sys.path.append(os.getcwd())

from app.database import SessionLocal
from app import models

db = SessionLocal()
try:
    case_id = 'bff270ca-c63c-4c32-8b15-152f5f9f616e'
    case = db.query(models.Case).filter(models.Case.id == case_id).first()
    if not case:
        print("Case not found")
    else:
        print(f"CASE: {case.case_ref_no}")
        print(f"CANDIDATE: {case.candidate.name if case.candidate else 'NONE'}")
        if case.candidate:
            print(f"DOCUMENTS: {case.candidate.documents}")
        
finally:
    db.close()
