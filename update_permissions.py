
import sys
import os

sys.path.append(r'd:\project\backend')

from app.database import SYNC_URL
from app.models import Role, User
from app.enums import UserRole
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

engine = create_engine(SYNC_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
db = SessionLocal()

try:
    # Update VERIFIER Role Permissions
    verifier_role = db.query(Role).filter(Role.name == "VERIFIER").first()
    if verifier_role:
        print("Updating VERIFIER permissions...")
        verifier_role.permissions = {
            "bvs": {
                "verification": {"read": True, "write": True}
            }
        }

    # Update QA Role Permissions
    qa_role = db.query(Role).filter(Role.name == "QA").first()
    if qa_role:
        print("Updating QA permissions...")
        qa_role.permissions = {
            "bvs": {
                "qc": {"read": True, "write": True},
                "verification": {"read": True}
            }
        }

    db.commit()
    print("Successfully updated role permissions.")

except Exception as e:
    db.rollback()
    print(f"Error: {e}")
finally:
    db.close()
