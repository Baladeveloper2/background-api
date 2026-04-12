import sys
import os
# Add the current directory to sys.path so 'app' can be found
sys.path.append(os.getcwd())

from app.database import SessionLocal
from app import models

def check_case(case_id):
    db = SessionLocal()
    try:
        case = db.query(models.Case).filter(models.Case.id == case_id).first()
        if not case:
            print("Case not found")
            return
        
        print(f"Case: {case.case_ref_no}")
        print(f"Candidate: {case.candidate.name if case.candidate else 'NO CANDIDATE'}")
        docs = (case.candidate.documents if case.candidate else []) or []
        print(f"Documents count: {len(docs)}")
        
        for i, doc in enumerate(docs):
            print(f"Doc {i}: {doc.get('original_filename')} - {doc.get('url')}")
    finally:
        db.close()

if __name__ == "__main__":
    check_case("5bafce6b-5990-4aab-9ee8-c6d07386fd7b")
