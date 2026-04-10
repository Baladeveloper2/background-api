import sys
import os
import uuid
from passlib.context import CryptContext

# Add the current directory to sys.path to import app
sys.path.append(os.getcwd())

from app.database import SessionLocal
from app import models
from app.enums import UserRole

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def create_qa_user():
    db = SessionLocal()
    try:
        # 1. Create QA Audit Role if not exists
        qa_role = db.query(models.Role).filter(models.Role.name == "QA Audit").first()
        if not qa_role:
            print("Creating QA Audit Role...")
            # Define broad permissions for QA
            permissions = {
                "bvs.verification": {"read": True, "write": True, "delete": False},
                "bvs.qc": {"read": True, "write": True, "delete": False},
                "bms.applicants": {"read": True, "write": True, "delete": False},
                "mis.report": {"read": True, "write": False, "delete": False}
            }
            qa_role = models.Role(
                id=str(uuid.uuid4()),
                name="QA Audit",
                description="Quality Assurance and Audit Governance Role",
                permissions=permissions
            )
            db.add(qa_role)
            db.flush()
        
        # 2. Create QA Audit User
        email = "qa.audit@cl-edge.com"
        existing_user = db.query(models.User).filter(models.User.email == email).first()
        if not existing_user:
            print(f"Creating QA Audit User: {email}")
            user = models.User(
                id=str(uuid.uuid4()),
                email=email,
                full_name="QA Audit Lead",
                hashed_password=pwd_context.hash("Admin@123"),
                role=models.UserRole.QA,
                role_id=qa_role.id,
                status="ACTIVE"
            )
            db.add(user)
        else:
            print(f"User {email} already exists.")
            existing_user.role_id = qa_role.id
            existing_user.role = models.UserRole.QA
        
        db.commit()
        print("Done.")

    except Exception as e:
        db.rollback()
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    create_qa_user()
