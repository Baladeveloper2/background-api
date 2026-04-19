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
            print("Creating QC Verification Role...")
            qa_role = models.Role(
                id=str(uuid.uuid4()),
                name="QC Verification",
                description="Quality Control and Verification Governance",
                permissions={"bms": True, "bvs": True, "verification": "write"}
            )
            db.add(qa_role)
            db.flush()
        
        # 2. Create QC Verification User
        email = "qc@bgv.com"
        user = db.query(models.User).filter(models.User.email == email).first()
        if not user:
            print(f"Creating QC Verification User: {email}")
            user = models.User(
                id=str(uuid.uuid4()),
                email=email,
                full_name="QC Verification Lead",
                hashed_password=pwd_context.hash("pass123"),
                role=models.UserRole.QC,
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
