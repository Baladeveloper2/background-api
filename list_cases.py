
from app.database import SessionLocal
from app.models import Case, Candidate, Customer
db = SessionLocal()
cases = db.query(Case).all()
print(f"Total: {len(cases)}")
for c in cases:
    cand_name = c.candidate.name if c.candidate else "N/A"
    cust_name = c.customer.name if c.customer else "N/A"
    print(f"CASE: {c.case_ref_no} | CAND: {cand_name} | CUST: {cust_name} | STATUS: {c.status}")
db.close()
