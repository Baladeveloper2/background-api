import sys
import os

# Add the current directory to sys.path to import app
sys.path.append(os.getcwd())

from app.database import SessionLocal
from app import models

def cleanup():
    db = SessionLocal()
    try:
        # Seeded customers to remove
        seeded_names = [
            "Infosys Ltd", "TCS Technologies", "Wipro Solutions", 
            "HCL Technologies", "Accenture India", "Google India", 
            "Amazon Dev Centre"
        ]
        
        # 1. Find the seeded customers
        customers = db.query(models.Customer).filter(models.Customer.name.in_(seeded_names)).all()
        customer_ids = [c.id for c in customers]
        
        if not customer_ids:
            print("No seeded customers found.")
            return

        # 2. Find and delete cases for these customers
        cases = db.query(models.Case).filter(models.Case.customer_id.in_(customer_ids)).all()
        case_ids = [c.id for c in cases]
        candidate_ids = [c.candidate_id for c in cases if c.candidate_id]
        
        # Delete verification checks first (foreign key constraint)
        db.query(models.VerificationCheck).filter(models.VerificationCheck.case_id.in_(case_ids)).delete(synchronize_session=False)
        
        # Delete cases
        db.query(models.Case).filter(models.Case.id.in_(case_ids)).delete(synchronize_session=False)
        
        # Delete candidates
        db.query(models.Candidate).filter(models.Candidate.id.in_(candidate_ids)).delete(synchronize_session=False)
        
        # Delete customers
        db.query(models.Customer).filter(models.Customer.id.in_(customer_ids)).delete(synchronize_session=False)
        
        db.commit()
        print(f"Removed {len(customer_ids)} customers, {len(case_ids)} cases, and their candidates.")

    except Exception as e:
        db.rollback()
        print(f"Error cleaning up data: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    cleanup()
