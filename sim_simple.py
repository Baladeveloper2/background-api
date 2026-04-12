
from app.database import SessionLocal
from app.models import Case
from app import schemas
from sqlalchemy.orm import joinedload

db = SessionLocal()
query = db.query(Case).options(
    joinedload(Case.candidate),
    joinedload(Case.customer),
    joinedload(Case.batch),
    joinedload(Case.assigned_user)
)
cases_models = query.all()
print(f"LEN: {len(cases_models)}")
for case in cases_models:
    name = case.candidate.name if case.candidate else "N/A"
    print(f"ID: {case.id} | NAME: {name}")
db.close()
