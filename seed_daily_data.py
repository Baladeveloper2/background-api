import sys
import os
import uuid
import random
from datetime import datetime, timedelta

# Add the current directory to sys.path to import app
sys.path.append(os.getcwd())

from app.database import SessionLocal, engine
from app import models
from app.enums import CaseStatus, CheckStatus

def seed():
    db = SessionLocal()
    try:
        # 1. Create Customers
        customers = [
            {"name": "Infosys Ltd", "city": "Bangalore"},
            {"name": "TCS Technologies", "city": "Mumbai"},
            {"name": "Wipro Solutions", "city": "Bangalore"},
            {"name": "HCL Technologies", "city": "Noida"},
            {"name": "Accenture India", "city": "Hyderabad"},
            {"name": "Google India", "city": "Hyderabad"},
            {"name": "Amazon Dev Centre", "city": "Bangalore"},
        ]
        
        db_customers = []
        for c in customers:
            # Check if exists
            existing = db.query(models.Customer).filter(models.Customer.name == c["name"]).first()
            if not existing:
                new_c = models.Customer(
                    id=str(uuid.uuid4()),
                    name=c["name"],
                    city=c["city"],
                    contact_person="Admin User",
                    phone="9876543210",
                    email=f"admin@{c['name'].lower().replace(' ', '')}.com",
                    address=f"123, Tech Park, {c['city']}",
                    report_format="Normal",
                    pricing_config={"employment": 500, "education": 300, "criminal": 200}
                )
                db.add(new_c)
                db_customers.append(new_c)
            else:
                db_customers.append(existing)
        
        db.commit()
        print(f"Seeded {len(db_customers)} customers.")

        # 2. Create Candidates and Cases
        first_names = ["Arjun", "Deepika", "Rahul", "Priya", "Amit", "Sneha", "Vikram", "Anjali", "Suresh", "Meera"]
        last_names = ["Kumar", "Sharma", "Singh", "Patel", "Verma", "Iyer", "Nair", "Reddy", "Gupta", "Das"]
        
        check_types = ["Employment", "Education", "Residence Address", "Reference", "Criminal", "ID"]
        
        # We want data for TODAY to show in the Daily Report
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        year = today.year
        
        # Create a Batch for today's cases
        db_batch = models.Batch(
            id=str(uuid.uuid4()),
            customer_id=db_customers[0].id, # Just pick first client for the batch
            batch_no=f"Batch_{year}_SEED_{random.randint(100, 999)}", # Special name for seed
            upload_date=today,
            cases_count=50,
            tat_days=10
        )
        db.add(db_batch)
        db.flush()
        
        total_cases = 50
        for i in range(total_cases):
            fname = random.choice(first_names)
            lname = random.choice(last_names)
            name = f"{fname} {lname}"
            email = f"{fname.lower()}.{lname.lower()}{random.randint(10,99)}@gmail.com"
            
            candidate = models.Candidate(
                id=str(uuid.uuid4()),
                name=name,
                email=email,
                phone=f"9{random.randint(100000000, 999999999)}",
                dob=datetime(1990 + random.randint(0, 15), random.randint(1, 12), random.randint(1, 28)).date(),
                created_at=today + timedelta(hours=random.randint(0, 8)) # Created today
            )
            db.add(candidate)
            db.flush()
            
            customer = random.choice(db_customers)
            
            # Decide status distribution
            probs = random.random()
            if probs < 0.4: # 40% Completed
                status = CaseStatus.COMPLETED
                completed_date = today + timedelta(hours=random.randint(9, 17))
            elif probs < 0.7: # 30% Pending/Interim
                status = random.choice([CaseStatus.PENDING, CaseStatus.VERIFICATION, CaseStatus.QC])
                completed_date = None
            else: # 30% Insufficient
                status = CaseStatus.INSUFFICIENT
                completed_date = None
                
            case = models.Case(
                id=str(uuid.uuid4()),
                case_ref_no=f"REF-{10000 + i}",
                customer_id=customer.id,
                candidate_id=candidate.id,
                batch_id=db_batch.id,
                status=status,
                received_date=today + timedelta(hours=random.randint(0, 4)), # Received today
                completed_date=completed_date,
                tat_days=random.randint(1, 10)
            )
            db.add(case)
            db.flush()
            
            # Add some checks
            num_checks = random.randint(2, 4)
            selected_checks = random.sample(check_types, num_checks)
            for ct in selected_checks:
                check_status = CheckStatus.INTERIM
                if status == CaseStatus.COMPLETED:
                    check_status = random.choice([CheckStatus.GREEN, CheckStatus.GREEN, CheckStatus.AMBER]) # Mostly green
                elif status == CaseStatus.INSUFFICIENT:
                    check_status = CheckStatus.RED
                
                check = models.VerificationCheck(
                    id=str(uuid.uuid4()),
                    case_id=case.id,
                    check_type=ct,
                    status=check_status,
                    verified_date=completed_date if completed_date else None
                )
                db.add(check)

        db.commit()
        print(f"Seeded {total_cases} cases for today.")

    except Exception as e:
        db.rollback()
        print(f"Error seeding data: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    seed()
