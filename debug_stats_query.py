from app.database import SessionLocal
from app import models
import traceback

db = SessionLocal()
try:
    print("Querying counts...")
    c1 = db.query(models.Candidate).count()
    print(f"Candidates: {c1}")
    c2 = db.query(models.Customer).count()
    print(f"Customers: {c2}")
    
    print("\nQuerying all customers...")
    custs = db.query(models.Customer).all()
    print(f"Fetched {len(custs)} customers")
    for c in custs:
        print(f"ID: {c.id}, Name: {c.name}, Active Status: {getattr(c, 'active_status', 'N/A')}")

except Exception as e:
    print(f"\nERROR DETECTED: {e}")
    traceback.print_exc()
finally:
    db.close()
