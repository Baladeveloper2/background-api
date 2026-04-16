
import sys
import os

sys.path.append(r'd:\project\backend')

from app.database import SYNC_URL
from app.models import Role, User
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

engine = create_engine(SYNC_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
db = SessionLocal()

try:
    # Update VERIFIER Role Permissions with flat keys
    verifier_role = db.query(Role).filter(Role.name == "VERIFIER").first()
    if verifier_role:
        print("Updating VERIFIER permissions to flat keys...")
        verifier_role.permissions = {
            "bvs.verification": {"read": True, "write": True}
        }

    # Update QA Role Permissions with flat keys
    qa_role = db.query(Role).filter(Role.name == "QA").first()
    if qa_role:
        print("Updating QA permissions to flat keys...")
        qa_role.permissions = {
            "bvs.qc": {"read": True, "write": True},
            "bvs.verification": {"read": True}
        }

    db.commit()
    print("Successfully updated role permissions with flat keys.")

except Exception as e:
    db.rollback()
    print(f"Error: {e}")
finally:
    db.close()
