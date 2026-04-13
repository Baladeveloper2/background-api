import os
import sys
# Add project root to path
sys.path.append(os.getcwd())

from app.database import SessionLocal
from app import models

db = SessionLocal()
try:
    candidates = db.query(models.Candidate).all()
    count = 0
    for c in candidates:
        if c.documents:
            print(f"CANDIDATE {c.id} ({c.name}) has {len(c.documents)} documents")
            for doc in c.documents:
                print(f"  - {doc.get('original_filename')} (Check: {doc.get('check_type')})")
            count += 1
    if count == 0:
        print("No candidates have documents.")
finally:
    db.close()
