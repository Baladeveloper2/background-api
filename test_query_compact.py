
from app.database import SessionLocal
from app.models import Case
db = SessionLocal()
cases = db.query(Case).all()
print(",".join([c.case_ref_no or "None" for c in cases]))
db.close()
